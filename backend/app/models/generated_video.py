"""GeneratedVideo ORM model — the final MP4 produced by a generation job."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.avatar import Avatar
    from app.models.generation_job import GenerationJob


class GeneratedVideo(Base):
    __tablename__ = "generated_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    avatar_id: Mapped[int] = mapped_column(
        ForeignKey("avatars.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped[GenerationJob] = relationship(
        back_populates="generated_video", foreign_keys=[job_id]
    )
    avatar: Mapped[Avatar] = relationship(back_populates="generated_videos")
