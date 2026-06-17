"""Generation orchestration service: validation + enqueue + owner-scoped reads."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import AvatarStatus, JobStatus
from app.models.generated_video import GeneratedVideo
from app.models.generation_job import GenerationJob
from app.pipelines.generation.steps import estimate_duration_seconds
from app.queue import db_queue
from app.services.avatar_service import AvatarNotFound, get_owned_avatar


class GenerationError(Exception):
    def __init__(self, message: str, *, code: str = "generation_error") -> None:
        super().__init__(message)
        self.code = code


def create_job(db: Session, *, user_id: int, avatar_id: int, script_text: str) -> GenerationJob:
    """Validate ownership + readiness + script length, then enqueue."""
    try:
        avatar = get_owned_avatar(db, user_id=user_id, avatar_id=avatar_id)
    except AvatarNotFound as exc:
        raise GenerationError("Avatar not found", code="not_found") from exc

    if avatar.status != AvatarStatus.ready:
        raise GenerationError(
            f"Avatar is not ready (status={avatar.status.value})", code="not_ready"
        )
    script_text = script_text.strip()
    if not script_text:
        raise GenerationError("Script is empty", code="empty_script")
    if len(script_text) > settings.MAX_SCRIPT_CHARS:
        raise GenerationError(
            f"Script exceeds {settings.MAX_SCRIPT_CHARS} characters", code="too_long"
        )

    return db_queue.enqueue_job(db, user_id=user_id, avatar_id=avatar_id, script_text=script_text)


def estimate_duration(script_text: str) -> float:
    return estimate_duration_seconds(script_text)


def list_jobs(
    db: Session, *, user_id: int, limit: int = 50, offset: int = 0
) -> list[GenerationJob]:
    return list(
        db.scalars(
            select(GenerationJob)
            .where(GenerationJob.user_id == user_id)
            .order_by(GenerationJob.queued_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def get_owned_job(db: Session, *, user_id: int, job_id: int) -> GenerationJob | None:
    return db.scalar(
        select(GenerationJob).where(GenerationJob.id == job_id, GenerationJob.user_id == user_id)
    )


def cancel_job(db: Session, job: GenerationJob) -> bool:
    """Mark a queued/processing job cancelled. Returns False if not cancellable."""
    if job.status not in (JobStatus.queued, JobStatus.processing):
        return False
    job.status = JobStatus.cancelled
    db.commit()
    return True


def list_videos(
    db: Session, *, user_id: int, limit: int = 50, offset: int = 0
) -> list[GeneratedVideo]:
    """List the user's generated videos (newest first), scoped via the job owner."""
    return list(
        db.scalars(
            select(GeneratedVideo)
            .join(GenerationJob, GeneratedVideo.job_id == GenerationJob.id)
            .where(GenerationJob.user_id == user_id)
            .order_by(GeneratedVideo.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


def get_owned_video(db: Session, *, user_id: int, video_id: int) -> GeneratedVideo | None:
    """Fetch a generated video only if its job belongs to the user (IDOR guard)."""
    return db.scalar(
        select(GeneratedVideo)
        .join(GenerationJob, GeneratedVideo.job_id == GenerationJob.id)
        .where(GeneratedVideo.id == video_id, GenerationJob.user_id == user_id)
    )
