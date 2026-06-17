"""Generation request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import JobStatus


class GenerateRequest(BaseModel):
    avatar_id: int
    script_text: str = Field(min_length=1, max_length=20_000)


class JobCreatedOut(BaseModel):
    job_id: int
    status: JobStatus
    estimated_duration_s: float


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    avatar_id: int
    status: JobStatus
    progress: int
    error_message: str | None
    output_video_id: int | None
    queued_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class GeneratedVideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int
    avatar_id: int
    duration_seconds: float | None
    resolution: str | None
    file_size_bytes: int | None
    created_at: datetime
