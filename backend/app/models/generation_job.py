"""GenerationJob ORM model — a row in the DB-backed generation queue.

Columns follow docs/DATABASE_SCHEMA.md, plus one documented addition:
`heartbeat_at`, used by the worker's stale-job reaper (VIDEO_GENERATION_PIPELINE.md
§7/§9) to detect and requeue jobs abandoned by a crashed worker.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import JobStatus, enum_col

if TYPE_CHECKING:
    from app.models.avatar import Avatar
    from app.models.generated_video import GeneratedVideo
    from app.models.user import User


class GenerationJob(Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (Index("ix_generation_jobs_status_queued_at", "status", "queued_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    avatar_id: Mapped[int] = mapped_column(
        ForeignKey("avatars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    script_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        enum_col(JobStatus, name="job_status"),
        nullable=False,
        default=JobStatus.queued,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_video_id: Mapped[int | None] = mapped_column(
        ForeignKey("generated_videos.id", ondelete="SET NULL"), nullable=True
    )
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="generation_jobs")
    avatar: Mapped[Avatar] = relationship(back_populates="generation_jobs")

    # Back-pointer to the produced video via generation_jobs.output_video_id
    # (post_update breaks the insert cycle; no back_populates → standalone).
    output_video: Mapped[GeneratedVideo | None] = relationship(
        foreign_keys=[output_video_id], post_update=True
    )
    # 1:1 owning side is generated_videos.job_id.
    generated_video: Mapped[GeneratedVideo | None] = relationship(
        back_populates="job",
        foreign_keys="GeneratedVideo.job_id",
        uselist=False,
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<GenerationJob id={self.id} status={self.status} progress={self.progress}>"
