"""Generation routes: create job, poll jobs, cancel, and download the final MP4."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.paths import is_within_storage
from app.db.session import get_db
from app.models.user import User
from app.schemas.generation import (
    GeneratedVideoOut,
    GenerateRequest,
    JobCreatedOut,
    JobOut,
)
from app.services import generation_service
from app.services.generation_service import GenerationError

router = APIRouter()

_ERROR_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "not_ready": status.HTTP_409_CONFLICT,
    "empty_script": 422,
    "too_long": 422,
}


@router.post("/generate", response_model=JobCreatedOut, status_code=status.HTTP_202_ACCEPTED)
def generate(
    body: GenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> JobCreatedOut:
    try:
        job = generation_service.create_job(
            db, user_id=user.id, avatar_id=body.avatar_id, script_text=body.script_text
        )
    except GenerationError as exc:
        raise HTTPException(
            status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=str(exc),
        ) from exc
    return JobCreatedOut(
        job_id=job.id,
        status=job.status,
        estimated_duration_s=generation_service.estimate_duration(job.script_text),
    )


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[JobOut]:
    return generation_service.list_jobs(db, user_id=user.id, limit=limit, offset=offset)


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> JobOut:
    job = generation_service.get_owned_job(db, user_id=user.id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> JobOut:
    job = generation_service.get_owned_job(db, user_id=user.id, job_id=job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not generation_service.cancel_job(db, job):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Job is not cancellable")
    return job


@router.get("/videos", response_model=list[GeneratedVideoOut])
def list_videos(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[GeneratedVideoOut]:
    return generation_service.list_videos(db, user_id=user.id, limit=limit, offset=offset)


@router.get("/videos/{video_id}/download")
def download_video(
    video_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> FileResponse:
    video = generation_service.get_owned_video(db, user_id=user.id, video_id=video_id)
    if video is None:
        # 404 (not 403) for a foreign/missing id — no existence leak (IDOR guard).
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    from pathlib import Path

    path = Path(video.file_path)
    # Defense in depth: never serve a file outside the storage root.
    if not is_within_storage(path) or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File unavailable")

    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"avatar_{video.avatar_id}_video_{video.id}.mp4",
    )
