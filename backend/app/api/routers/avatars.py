"""Avatar domain routes: CRUD, script generation, video upload, status polling.

Every route is owner-scoped via get_current_active_user + get_owned_avatar, so a
user can only ever touch their own avatars (missing/foreign → 404, no leak).
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.session import get_db
from app.models.training_video import TrainingVideo
from app.models.user import User
from app.pipelines.avatar_creation.runner import cleanup_avatar_storage, run_avatar_pipeline
from app.schemas.avatar import (
    AvatarCreate,
    AvatarOut,
    AvatarStatusOut,
    ScriptOut,
    TrainingVideoOut,
)
from app.services import avatar_service, script_service, upload_service
from app.services.avatar_service import AvatarNotFound
from app.services.upload_service import UploadError

router = APIRouter()


def _require_avatar(db: Session, user: User, avatar_id: int):
    try:
        return avatar_service.get_owned_avatar(db, user_id=user.id, avatar_id=avatar_id)
    except AvatarNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found"
        ) from exc


@router.post("", response_model=AvatarOut, status_code=status.HTTP_201_CREATED)
def create_avatar(
    body: AvatarCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> AvatarOut:
    return avatar_service.create_avatar(db, user_id=user.id, name=body.name)


@router.get("", response_model=list[AvatarOut])
def list_avatars(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[AvatarOut]:
    return avatar_service.list_avatars(db, user_id=user.id)


@router.get("/{avatar_id}", response_model=AvatarOut)
def get_avatar(
    avatar_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> AvatarOut:
    return _require_avatar(db, user, avatar_id)


@router.delete("/{avatar_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_avatar(
    avatar_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> None:
    _require_avatar(db, user, avatar_id)
    avatar_service.delete_avatar(db, user_id=user.id, avatar_id=avatar_id)
    cleanup_avatar_storage(avatar_id)


@router.post("/{avatar_id}/script", response_model=ScriptOut, status_code=status.HTTP_201_CREATED)
def generate_script(
    avatar_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ScriptOut:
    _require_avatar(db, user, avatar_id)
    return script_service.create_script_for_avatar(db, user_id=user.id, avatar_id=avatar_id)


@router.get("/{avatar_id}/script", response_model=ScriptOut)
def get_script(
    avatar_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> ScriptOut:
    _require_avatar(db, user, avatar_id)
    script = script_service.get_latest_script(db, avatar_id=avatar_id)
    if script is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No script yet")
    return script


@router.post(
    "/{avatar_id}/video",
    response_model=TrainingVideoOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_video(
    avatar_id: int,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> TrainingVideoOut:
    _require_avatar(db, user, avatar_id)
    try:
        video = await upload_service.save_training_video(
            db, user_id=user.id, avatar_id=avatar_id, file=file
        )
    except UploadError as exc:
        code = (
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            if exc.too_large
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc

    # Associate the latest script (the passage the user just read), if any.
    latest = script_service.get_latest_script(db, avatar_id=avatar_id)
    if latest is not None:
        video.script_id = latest.id
        db.commit()
        db.refresh(video)

    # Kick the creation pipeline asynchronously (Phase 4 replaces this with a
    # durable DB-backed queue + worker).
    background.add_task(run_avatar_pipeline, avatar_id)
    return video


@router.get("/{avatar_id}/status", response_model=AvatarStatusOut)
def avatar_status(
    avatar_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> AvatarStatusOut:
    avatar = _require_avatar(db, user, avatar_id)
    video = (
        db.query(TrainingVideo)
        .filter_by(avatar_id=avatar_id)
        .order_by(TrainingVideo.created_at.desc(), TrainingVideo.id.desc())
        .first()
    )
    return AvatarStatusOut(
        avatar_id=avatar.id,
        status=avatar.status,
        error_message=avatar.error_message,
        video=video,
        voice_model=avatar.voice_model,
    )
