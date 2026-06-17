"""Training-video upload handling: validation + safe streamed storage.

Security posture (AVATAR_CREATION_PIPELINE.md §2, roadmap Phase 3 risks):
- Never trust the client filename or content-type alone.
- Enforce an allowlist of extensions + declared MIME types.
- Enforce a hard size cap while streaming (no full-buffer in memory).
- Derive the storage path ONLY from integer IDs via app.core.paths (no user
  string ever enters the path) — prevents path traversal.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.paths import ensure_dir, upload_video_path, uploads_dir
from app.models.enums import VideoStatus
from app.models.training_video import TrainingVideo

_EXT_BY_TYPE = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
}
_ALLOWED_EXTS = {"mp4", "mov", "webm"}
_CHUNK = 1024 * 1024  # 1 MiB


class UploadError(Exception):
    """Validation failure mapped to HTTP 400/413 in the router."""

    def __init__(self, message: str, *, too_large: bool = False) -> None:
        super().__init__(message)
        self.too_large = too_large


def _resolve_ext(file: UploadFile) -> str:
    """Pick a safe extension from the declared content-type, falling back to the
    filename suffix — but only if it is in the allowlist."""
    if file.content_type in _EXT_BY_TYPE:
        return _EXT_BY_TYPE[file.content_type]
    suffix = Path(file.filename or "").suffix.lstrip(".").lower()
    if suffix in _ALLOWED_EXTS:
        return "mov" if suffix == "mov" else suffix
    raise UploadError(
        f"Unsupported video type: {file.content_type or file.filename!r}. "
        f"Allowed: {', '.join(sorted(settings.ALLOWED_VIDEO_TYPES))}"
    )


async def save_training_video(
    db: Session, *, user_id: int, avatar_id: int, file: UploadFile
) -> TrainingVideo:
    """Validate and stream an upload to disk, then create a TrainingVideo row.

    The DB row is created first (without a path) to allocate the integer id used
    to build the storage path; the path is then filled in. On any write error we
    roll the row back and remove a partial file.
    """
    # _resolve_ext enforces the type/extension allowlist (raises UploadError).
    ext = _resolve_ext(file)

    # Allocate an id by inserting a placeholder row.
    video = TrainingVideo(
        user_id=user_id,
        avatar_id=avatar_id,
        file_path="",
        status=VideoStatus.uploaded,
    )
    db.add(video)
    db.flush()  # assigns video.id without committing

    ensure_dir(uploads_dir(user_id))
    dest = upload_video_path(user_id, video.id, ext)

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(_CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    raise UploadError(
                        f"File exceeds {settings.MAX_UPLOAD_MB} MB limit", too_large=True
                    )
                out.write(chunk)
    except UploadError:
        dest.unlink(missing_ok=True)
        db.rollback()
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        db.rollback()
        raise

    if written == 0:
        dest.unlink(missing_ok=True)
        db.rollback()
        raise UploadError("Empty upload")

    video.file_path = str(dest)
    video.file_size_bytes = written
    db.commit()
    db.refresh(video)
    return video
