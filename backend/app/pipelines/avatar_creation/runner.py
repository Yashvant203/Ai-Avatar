"""Avatar-creation pipeline orchestration.

Drives the avatar through pending → processing → ready/failed, calling each stage
in the order documented in AVATAR_CREATION_PIPELINE.md and persisting status +
sub-asset (training_video, voice_model) transitions along the way.

The selected backend (real or stub) supplies the ML-heavy operations; ffmpeg
audio/frame extraction is real in both modes.
"""

from __future__ import annotations

import shutil

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.paths import (
    avatar_dir,
    avatar_driving_path,
    avatar_face_path,
    avatar_profile_path,
    avatar_thumbnail_path,
    ensure_dir,
    relpath,
    voice_dir,
    voice_model_path,
    voice_reference_path,
    voice_source_audio_path,
)
from app.db.session import SessionLocal
from app.models.avatar import Avatar
from app.models.enums import AvatarStatus, VideoStatus, VoiceStatus
from app.models.training_script import TrainingScript
from app.models.training_video import TrainingVideo
from app.models.voice_model import VoiceModel
from app.pipelines.avatar_creation.errors import VIDEO_INPUT_ERRORS, PipelineError
from app.pipelines.avatar_creation.ml.loaders import get_backend
from app.pipelines.avatar_creation.steps import extract_audio, extract_face, profile
from app.pipelines.avatar_creation.steps.clone_voice import build_voice_model
from app.pipelines.avatar_creation.steps.liveportrait_prep import prep_driving

logger = get_logger("pipeline.runner")


def _get_or_create_voice(db: Session, avatar_id: int) -> VoiceModel:
    voice = db.query(VoiceModel).filter_by(avatar_id=avatar_id).one_or_none()
    if voice is None:
        voice = VoiceModel(avatar_id=avatar_id, status=VoiceStatus.pending)
        db.add(voice)
        db.commit()
        db.refresh(voice)
    return voice


def run_avatar_pipeline(avatar_id: int, *, db_factory=SessionLocal) -> None:
    """Run the full avatar-creation pipeline for `avatar_id`.

    Safe to call from a FastAPI BackgroundTask. Creates its own DB session via
    `db_factory` (overridable in tests).
    """
    db = db_factory()
    frame_dir = avatar_dir(avatar_id) / "_frames"
    try:
        avatar = db.get(Avatar, avatar_id)
        if avatar is None:
            logger.warning("pipeline: avatar %s gone, aborting", avatar_id)
            return
        video = (
            db.query(TrainingVideo)
            .filter_by(avatar_id=avatar_id)
            .order_by(TrainingVideo.created_at.desc(), TrainingVideo.id.desc())
            .first()
        )
        if video is None:
            avatar.status = AvatarStatus.failed
            avatar.error_message = "NO_VIDEO"
            db.commit()
            return
        script = (
            db.query(TrainingScript)
            .filter_by(avatar_id=avatar_id)
            .order_by(TrainingScript.created_at.desc())
            .first()
        )
        voice = _get_or_create_voice(db, avatar_id)
        backend = get_backend()

        ensure_dir(avatar_dir(avatar_id))
        ensure_dir(voice_dir(avatar_id))

        try:
            avatar.status = AvatarStatus.processing
            avatar.error_message = None
            video.status = VideoStatus.processing
            db.commit()

            # Stage 1 — validate + extract audio
            video_meta = extract_audio.probe_video(video.file_path)
            src_audio = voice_source_audio_path(avatar_id)
            extract_audio.extract_source_audio(video.file_path, src_audio)

            # persist probed video metadata
            video.duration_seconds = video_meta.get("duration_seconds")
            if video_meta.get("width") and video_meta.get("height"):
                video.resolution = f"{video_meta['width']}x{video_meta['height']}"
            db.commit()

            # Stage 3 — reference selection
            ref = voice_reference_path(avatar_id)
            ref_meta = backend.select_reference(
                src_audio, ref, script_text=script.content if script else None
            )

            # Stage 4 — voice clone (F5-TTS reference artifact)
            model_pt = voice_model_path(avatar_id)
            voice_meta = build_voice_model(
                db,
                voice=voice,
                backend=backend,
                reference=ref,
                transcript=ref_meta["transcript"],
                out_model=model_pt,
                sample_rate=voice.sample_rate,
            )

            # Stage 5 — frames + best face
            extract_face.sample_frames(video.file_path, frame_dir)
            face_png = avatar_face_path(avatar_id)
            thumb_png = avatar_thumbnail_path(avatar_id)
            face_meta = backend.select_best_face(frame_dir, face_png, thumb_png)

            # Stage 6 — head-pose statistics
            pose_stats = profile.head_pose_stats(face_meta.get("pose_samples", []))

            # Stage 7 — derive the avatar's driving clip (motion profile) from its upload
            driving_mp4 = avatar_driving_path(avatar_id)
            motion_meta = prep_driving(
                backend, source_video=video.file_path, out_driving=driving_mp4
            )

            # Stage 8 — assemble profile.json + checksum
            artifact_paths = {
                "face": relpath(face_png),
                "_face_abs": str(face_png),
                "thumbnail": relpath(thumb_png),
                "motion_template": relpath(driving_mp4),
                "_motion_abs": str(driving_mp4),
                "voice_model": relpath(model_pt),
                "_voice_model_abs": str(model_pt),
                "reference": relpath(ref),
                "_reference_abs": str(ref),
                "source_video": relpath(video.file_path),
            }
            video_meta["video_id"] = video.id
            prof = profile.assemble_profile(
                avatar_id=avatar.id,
                user_id=avatar.user_id,
                voice_model_id=voice.id,
                face_meta=face_meta,
                pose_stats=pose_stats,
                motion_meta=motion_meta,
                ref_meta=ref_meta,
                voice_meta=voice_meta,
                video_meta=video_meta,
                artifact_paths=artifact_paths,
            )
            profile.write_json(avatar_profile_path(avatar_id), prof)

            # Link + finalize
            avatar.source_video_id = video.id
            avatar.voice_model_id = voice.id
            avatar.profile_path = str(avatar_profile_path(avatar_id))
            avatar.thumbnail_path = str(thumb_png)
            avatar.status = AvatarStatus.ready
            avatar.error_message = None
            video.status = VideoStatus.analyzed
            db.commit()
            logger.info("avatar %s ready (backend=%s)", avatar_id, backend.name)

        except PipelineError as exc:
            db.rollback()
            avatar.status = AvatarStatus.failed
            avatar.error_message = exc.code
            if exc.code in VIDEO_INPUT_ERRORS:
                video.status = VideoStatus.failed
            db.commit()
            logger.warning("avatar %s failed: %s", avatar_id, exc.code)
            raise
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            avatar.status = AvatarStatus.failed
            avatar.error_message = f"INTERNAL: {str(exc)[:300]}"
            db.commit()
            logger.exception("avatar %s internal failure", avatar_id)
            raise
    finally:
        db.close()
        shutil.rmtree(frame_dir, ignore_errors=True)


def cleanup_avatar_storage(avatar_id: int) -> None:
    """Remove on-disk artifacts for an avatar (used on delete)."""
    for d in (avatar_dir(avatar_id), voice_dir(avatar_id)):
        shutil.rmtree(d, ignore_errors=True)
