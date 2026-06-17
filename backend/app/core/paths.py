"""Path-traversal-safe storage path builders.

All artifact paths are derived here from integer IDs (never from raw user input),
and every returned path is asserted to live under STORAGE_DIR. This is the single
choke point that prevents `../` traversal and absolute-path escapes.

Canonical layout (docs/SYSTEM_ARCHITECTURE.md, AVATAR_CREATION_PIPELINE.md):
    storage/uploads/{user_id}/{video_id}.mp4
    storage/avatars/{avatar_id}/{profile.json, face.png, motion_template.pkl, thumbnail.png}
    storage/voices/{avatar_id}/{reference.wav, source_audio.wav, model.pt}
    storage/outputs/{job_id}/output.mp4
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import settings

# Absolute, resolved storage root. Everything must stay under this.
STORAGE_ROOT: Path = settings.STORAGE_DIR.resolve()


def _safe_join(*parts: str | int) -> Path:
    """Join parts under STORAGE_ROOT and assert the result cannot escape it."""
    candidate = STORAGE_ROOT.joinpath(*[str(p) for p in parts]).resolve()
    if candidate != STORAGE_ROOT and STORAGE_ROOT not in candidate.parents:
        raise ValueError(f"Refusing path outside storage root: {candidate}")
    return candidate


def ensure_dir(path: Path) -> Path:
    """Create a directory (and parents) if missing; return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


# --- uploads ---------------------------------------------------------------
def uploads_dir(user_id: int) -> Path:
    return _safe_join("uploads", user_id)


def upload_video_path(user_id: int, video_id: int, ext: str = "mp4") -> Path:
    ext = ext.lstrip(".").lower()
    return _safe_join("uploads", user_id, f"{video_id}.{ext}")


# --- avatars ---------------------------------------------------------------
def avatar_dir(avatar_id: int) -> Path:
    return _safe_join("avatars", avatar_id)


def avatar_profile_path(avatar_id: int) -> Path:
    return _safe_join("avatars", avatar_id, "profile.json")


def avatar_face_path(avatar_id: int) -> Path:
    return _safe_join("avatars", avatar_id, "face.png")


def avatar_thumbnail_path(avatar_id: int) -> Path:
    return _safe_join("avatars", avatar_id, "thumbnail.png")


def avatar_motion_template_path(avatar_id: int) -> Path:
    return _safe_join("avatars", avatar_id, "motion_template.pkl")


# --- voices ----------------------------------------------------------------
def voice_dir(avatar_id: int) -> Path:
    return _safe_join("voices", avatar_id)


def voice_source_audio_path(avatar_id: int) -> Path:
    return _safe_join("voices", avatar_id, "source_audio.wav")


def voice_reference_path(avatar_id: int) -> Path:
    return _safe_join("voices", avatar_id, "reference.wav")


def voice_model_path(avatar_id: int) -> Path:
    return _safe_join("voices", avatar_id, "model.pt")


# --- outputs (generation jobs) ---------------------------------------------
def output_dir(job_id: int) -> Path:
    return _safe_join("outputs", job_id)


def output_speech_path(job_id: int) -> Path:
    return _safe_join("outputs", job_id, "speech.wav")


def output_frames_dir(job_id: int) -> Path:
    return _safe_join("outputs", job_id, "frames")


def output_animated_path(job_id: int) -> Path:
    return _safe_join("outputs", job_id, "animated.mp4")


def output_lipsync_path(job_id: int) -> Path:
    return _safe_join("outputs", job_id, "lipsync.mp4")


def output_video_final_path(job_id: int) -> Path:
    return _safe_join("outputs", job_id, "output.mp4")


def output_thumb_path(job_id: int) -> Path:
    return _safe_join("outputs", job_id, "thumb.jpg")


def is_within_storage(path: Path | str) -> bool:
    """True if `path` resolves to a location inside STORAGE_ROOT (download guard)."""
    p = Path(path).resolve()
    return p == STORAGE_ROOT or STORAGE_ROOT in p.parents


def relpath(path: Path | str) -> str:
    """Return a path relative to STORAGE_ROOT (for storing in profile.json/DB)."""
    p = Path(path).resolve()
    try:
        return str(p.relative_to(STORAGE_ROOT))
    except ValueError:
        return str(p)
