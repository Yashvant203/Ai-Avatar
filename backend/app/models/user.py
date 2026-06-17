"""User ORM model.

Canonical column set per docs/DATABASE_SCHEMA.md. The cross-model relationships
defined there (avatars, training_scripts, training_videos, generation_jobs) are
intentionally omitted until those models exist (Phase 3/4); they will be added
with matching back_populates then. Adding them now would break mapper
configuration because the target classes are not yet registered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.avatar import Avatar
    from app.models.generation_job import GenerationJob
    from app.models.training_script import TrainingScript
    from app.models.training_video import TrainingVideo


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    avatars: Mapped[list[Avatar]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    training_scripts: Mapped[list[TrainingScript]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    training_videos: Mapped[list[TrainingVideo]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    generation_jobs: Mapped[list[GenerationJob]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<User id={self.id} email={self.email!r}>"
