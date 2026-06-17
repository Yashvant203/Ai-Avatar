"""Generation job orchestration: F5-TTS → LivePortrait → MuseTalk → ffmpeg mux.

Drives one claimed job to completion with banded progress, cancellation checks
between stages, and failure handling per VIDEO_GENERATION_PIPELINE.md. The
selected backend supplies the ML stages; ffmpeg muxing is shared.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import (
    avatar_face_path,
    ensure_dir,
    output_animated_path,
    output_dir,
    output_lipsync_path,
    output_speech_path,
    output_thumb_path,
    output_video_final_path,
    voice_reference_path,
)
from app.models.enums import JobStatus
from app.models.generated_video import GeneratedVideo
from app.models.generation_job import GenerationJob
from app.pipelines.generation import progress, steps
from app.pipelines.generation.ml.backends import GenerationBackend
from app.pipelines.generation.ml.loaders import get_generation_backend
from app.queue import db_queue

logger = get_logger("generation.orchestrator")


class JobCancelled(Exception):
    """Raised when a job is cancelled mid-run."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _guard_cancel(db: Session, job: GenerationJob) -> None:
    if db_queue.is_cancelled(db, job):
        raise JobCancelled()


def _finalize_storage(db: Session, job: GenerationJob, out_video: Path) -> GeneratedVideo:
    meta = steps.probe_output(out_video)
    width, height = meta.get("width"), meta.get("height")
    video = GeneratedVideo(
        job_id=job.id,
        avatar_id=job.avatar_id,
        file_path=str(out_video),
        duration_seconds=meta.get("duration_seconds"),
        resolution=f"{width}x{height}" if width and height else None,
        file_size_bytes=out_video.stat().st_size,
    )
    db.add(video)
    db.flush()  # assign video.id
    job.output_video_id = video.id
    job.status = JobStatus.completed
    job.progress = 100
    job.completed_at = _utcnow()
    job.error_message = None
    db.commit()
    return video


def _cleanup_intermediates(out_dir: Path) -> None:
    """On success: drop the largest artifact (frames/) immediately."""
    shutil.rmtree(out_dir / "frames", ignore_errors=True)


def run_generation_job(
    db: Session, job: GenerationJob, backend: GenerationBackend | None = None
) -> GeneratedVideo | None:
    """Run all four stages for an already-claimed (processing) job."""
    backend = backend or get_generation_backend()
    out = ensure_dir(output_dir(job.id))
    fps = settings.OUTPUT_FPS

    try:
        _guard_cancel(db, job)

        # Stage 1 — F5-TTS speech
        db_queue.set_progress(db, job, progress.band_start("f5_tts"))
        voice_ref = voice_reference_path(job.avatar_id)
        duration = steps.estimate_duration_seconds(job.script_text)
        speech = output_speech_path(job.id)
        duration = backend.synthesize_speech(
            speech,
            script_text=job.script_text,
            voice_ref=voice_ref if voice_ref.exists() else None,
            duration_s=duration,
        )
        db_queue.set_progress(db, job, progress.band_end("f5_tts"))
        _guard_cancel(db, job)

        # Stage 2 — LivePortrait animation
        db_queue.set_progress(db, job, progress.band_start("liveportrait"))
        face = avatar_face_path(job.avatar_id)
        animated = output_animated_path(job.id)
        backend.animate(
            animated, face=face if face.exists() else None, duration_s=duration, fps=fps
        )
        db_queue.set_progress(db, job, progress.band_end("liveportrait"))
        _guard_cancel(db, job)

        # Stage 3 — MuseTalk lip-sync
        db_queue.set_progress(db, job, progress.band_start("musetalk"))
        lipsync = output_lipsync_path(job.id)
        backend.lipsync(animated, speech, lipsync)
        db_queue.set_progress(db, job, progress.band_end("musetalk"))
        _guard_cancel(db, job)

        # Stage 4 — ffmpeg mux + thumbnail
        db_queue.set_progress(db, job, progress.band_start("mux"))
        final = output_video_final_path(job.id)
        steps.mux_output(lipsync, speech, final, fps=fps)
        steps.make_thumbnail(final, output_thumb_path(job.id))
        db_queue.set_progress(db, job, progress.band_end("mux"))

        video = _finalize_storage(db, job, final)
        _cleanup_intermediates(out)
        logger.info("job %s completed (backend=%s)", job.id, backend.name)
        return video

    except JobCancelled:
        db.rollback()
        job.status = JobStatus.cancelled
        job.completed_at = _utcnow()
        db.commit()
        # Never serve a partial file.
        output_video_final_path(job.id).unlink(missing_ok=True)
        logger.info("job %s cancelled", job.id)
        return None
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job.status = JobStatus.failed
        job.error_message = str(exc)[:500]
        job.completed_at = _utcnow()
        db.commit()
        # Remove any partial/zero-byte output so it is never downloadable.
        final_path = output_video_final_path(job.id)
        if final_path.exists() and final_path.stat().st_size == 0:
            final_path.unlink(missing_ok=True)
        logger.exception("job %s failed", job.id)
        raise
