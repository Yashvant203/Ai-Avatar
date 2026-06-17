"""TrainingScript ORM model — the passage a user reads while recording."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.avatar import Avatar
    from app.models.training_video import TrainingVideo
    from app.models.user import User


class TrainingScript(Base):
    __tablename__ = "training_scripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    avatar_id: Mapped[int | None] = mapped_column(
        ForeignKey("avatars.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="training_scripts")
    avatar: Mapped[Avatar | None] = relationship(
        back_populates="training_scripts", foreign_keys=[avatar_id]
    )
    training_videos: Mapped[list[TrainingVideo]] = relationship(back_populates="script")
