"""TrainingVideo ORM model — the uploaded source recording."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import VideoStatus, enum_col

if TYPE_CHECKING:
    from app.models.avatar import Avatar
    from app.models.training_script import TrainingScript
    from app.models.user import User


class TrainingVideo(Base):
    __tablename__ = "training_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    avatar_id: Mapped[int | None] = mapped_column(
        ForeignKey("avatars.id", ondelete="SET NULL"), nullable=True, index=True
    )
    script_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_scripts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(16), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[VideoStatus] = mapped_column(
        enum_col(VideoStatus, name="video_status"),
        nullable=False,
        default=VideoStatus.uploaded,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="training_videos")
    avatar: Mapped[Avatar | None] = relationship(
        back_populates="training_videos", foreign_keys=[avatar_id]
    )
    script: Mapped[TrainingScript | None] = relationship(back_populates="training_videos")
