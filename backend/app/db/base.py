"""SQLAlchemy declarative Base and model import aggregation point.

Alembic's `env.py` imports `Base` from here so that `Base.metadata` reflects
every table. As models are added in later phases, import them at the bottom of
this module so autogenerate sees them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class TimestampMixin:
    """Adds UTC created_at / updated_at columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# NOTE: Do NOT import models here — models import Base from this module, so a
# back-import would create a circular import. Models are registered instead via
# `app/models/__init__.py` (loaded by Alembic's `import app.models` and by app
# startup). Keep this module dependency-free.
