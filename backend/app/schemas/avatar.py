"""Avatar-domain request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AvatarStatus, VideoStatus, VoiceStatus


class AvatarCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class AvatarOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    status: AvatarStatus
    profile_path: str | None
    thumbnail_path: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ScriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    avatar_id: int | None
    content: str
    word_count: int
    language: str
    created_at: datetime


class TrainingVideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: VideoStatus
    duration_seconds: float | None
    resolution: str | None
    created_at: datetime


class VoiceModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: VoiceStatus
    sample_rate: int


class AvatarStatusOut(BaseModel):
    """Aggregated status for client polling (GET /api/avatars/{id}/status)."""

    avatar_id: int
    status: AvatarStatus
    error_message: str | None
    video: TrainingVideoOut | None
    voice_model: VoiceModelOut | None
