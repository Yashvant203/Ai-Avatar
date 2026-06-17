"""Shared string-valued enums and the enum-column helper.

Enums are persisted as their lowercase *value* (VARCHAR + CHECK), not the Python
member name, per docs/DATABASE_SCHEMA.md.
"""

from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum


class AvatarStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class VideoStatus(str, enum.Enum):
    uploaded = "uploaded"
    processing = "processing"
    analyzed = "analyzed"
    failed = "failed"


class VoiceStatus(str, enum.Enum):
    pending = "pending"
    training = "training"
    ready = "ready"
    failed = "failed"


class JobStatus(str, enum.Enum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


def enum_col(py_enum: type[enum.Enum], *, name: str) -> SAEnum:
    """SAEnum that persists the value (lowercase string), not the member name."""
    return SAEnum(
        py_enum,
        name=name,
        native_enum=False,  # store as VARCHAR + CHECK
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
