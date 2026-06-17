"""DB-backed generation queue.

The `generation_jobs` table *is* the queue (no Redis/Celery). A single worker
plus WAL keeps SQLite contention a non-issue; the conditional-UPDATE claim stays
correct even if a second worker is ever added (VIDEO_GENERATION_PIPELINE.md §7).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import JobStatus
from app.models.generation_job import GenerationJob

logger = get_logger("queue")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_job(db: Session, *, user_id: int, avatar_id: int, script_text: str) -> GenerationJob:
    job = GenerationJob(
        user_id=user_id,
        avatar_id=avatar_id,
        script_text=script_text,
        status=JobStatus.queued,
        progress=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next_job(db: Session) -> GenerationJob | None:
    """Atomically claim the oldest queued job (queued → processing).

    The conditional UPDATE only flips a row that is *still* queued, so rowcount==1
    proves exclusive ownership.
    """
    job = db.scalar(
        select(GenerationJob)
        .where(GenerationJob.status == JobStatus.queued)
        .order_by(GenerationJob.queued_at.asc())
        .limit(1)
    )
    if job is None:
        return None

    now = _utcnow()
    updated = (
        db.query(GenerationJob)
        .filter(GenerationJob.id == job.id, GenerationJob.status == JobStatus.queued)
        .update(
            {
                "status": JobStatus.processing,
                "started_at": now,
                "heartbeat_at": now,
                "progress": 1,
            },
            synchronize_session=False,
        )
    )
    db.commit()
    if updated != 1:
        return None  # lost the race; caller loops again
    db.refresh(job)
    return job


def requeue_zombie_jobs(db: Session) -> int:
    """Requeue jobs stuck in `processing` past the heartbeat timeout (crashed worker).

    Returns the number of jobs requeued.
    """
    cutoff = _utcnow() - timedelta(seconds=settings.JOB_HEARTBEAT_TIMEOUT)
    stale = list(
        db.scalars(
            select(GenerationJob).where(
                GenerationJob.status == JobStatus.processing,
                GenerationJob.heartbeat_at.is_not(None),
                GenerationJob.heartbeat_at < cutoff,
            )
        )
    )
    for job in stale:
        job.status = JobStatus.queued
        job.started_at = None
        job.heartbeat_at = None
        job.progress = 0
        logger.warning("requeued zombie job %s", job.id)
    if stale:
        db.commit()
    return len(stale)


def set_progress(db: Session, job: GenerationJob, pct: int) -> None:
    """Monotonically bump progress (capped at 98 until finalize) + heartbeat."""
    job.progress = max(job.progress, min(98, pct))
    job.heartbeat_at = _utcnow()
    db.commit()


def is_cancelled(db: Session, job: GenerationJob) -> bool:
    db.refresh(job)
    return job.status == JobStatus.cancelled
