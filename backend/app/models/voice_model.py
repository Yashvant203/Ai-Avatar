"""VoiceModel ORM model — 1:1 with Avatar; holds the F5-TTS voice profile artifact."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import VoiceStatus, enum_col

if TYPE_CHECKING:
    from app.models.avatar import Avatar


class VoiceModel(Base):
    __tablename__ = "voice_models"
    __table_args__ = (UniqueConstraint("avatar_id", name="uq_voice_models_avatar_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    avatar_id: Mapped[int] = mapped_column(
        ForeignKey("avatars.id", ondelete="CASCADE"), nullable=False
    )
    model_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    reference_audio_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sample_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=24000)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[VoiceStatus] = mapped_column(
        enum_col(VoiceStatus, name="voice_status"),
        nullable=False,
        default=VoiceStatus.pending,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # owning side of the 1:1 (this FK, voice_models.avatar_id, is the source of truth)
    avatar_ref: Mapped[Avatar] = relationship(
        back_populates="voice_model", foreign_keys=[avatar_id]
    )
