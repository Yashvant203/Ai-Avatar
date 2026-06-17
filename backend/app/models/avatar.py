"""Avatar ORM model — the reusable avatar profile.

Columns follow docs/DATABASE_SCHEMA.md, with one documented addition:
`error_message`, which the avatar-creation pipeline (AVATAR_CREATION_PIPELINE.md
§9) writes on failure so GET /api/avatars/{id}/status can surface a reason.

Relationships to GenerationJob / GeneratedVideo are intentionally omitted until
those models are registered in Phase 4 (adding them now would break mapper
configuration).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import AvatarStatus, enum_col

if TYPE_CHECKING:
    from app.models.generated_video import GeneratedVideo
    from app.models.generation_job import GenerationJob
    from app.models.training_script import TrainingScript
    from app.models.training_video import TrainingVideo
    from app.models.user import User
    from app.models.voice_model import VoiceModel


class Avatar(TimestampMixin, Base):
    __tablename__ = "avatars"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[AvatarStatus] = mapped_column(
        enum_col(AvatarStatus, name="avatar_status"),
        nullable=False,
        default=AvatarStatus.pending,
    )
    profile_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_video_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_videos.id", ondelete="SET NULL"), nullable=True
    )
    # Denormalized back-pointer column kept for schema fidelity
    # (docs/DATABASE_SCHEMA.md). It is set manually by the pipeline; the ORM
    # relationship below is routed through the single owning FK
    # voice_models.avatar_id to keep a clean, non-cyclic 1:1 mapping.
    voice_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("voice_models.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="avatars")

    # Children whose avatar_id is NOT NULL: they are owned by the avatar and are
    # removed with it. cascade + passive_deletes lets the DB ON DELETE CASCADE do
    # the work instead of the ORM trying to NULL a NOT NULL column.
    # 1:1 via the unique owning FK voice_models.avatar_id.
    voice_model: Mapped[VoiceModel | None] = relationship(
        back_populates="avatar_ref",
        foreign_keys="VoiceModel.avatar_id",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    generation_jobs: Mapped[list[GenerationJob]] = relationship(
        back_populates="avatar", cascade="all, delete-orphan", passive_deletes=True
    )
    generated_videos: Mapped[list[GeneratedVideo]] = relationship(
        back_populates="avatar", cascade="all, delete-orphan", passive_deletes=True
    )

    # Recordings/scripts belong to the user; on avatar delete their avatar_id is
    # set NULL by the DB (FK ondelete=SET NULL), so don't delete or ORM-nullify.
    training_videos: Mapped[list[TrainingVideo]] = relationship(
        back_populates="avatar", foreign_keys="TrainingVideo.avatar_id", passive_deletes=True
    )
    training_scripts: Mapped[list[TrainingScript]] = relationship(
        back_populates="avatar", foreign_keys="TrainingScript.avatar_id", passive_deletes=True
    )
    source_video: Mapped[TrainingVideo | None] = relationship(foreign_keys=[source_video_id])

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Avatar id={self.id} name={self.name!r} status={self.status}>"
