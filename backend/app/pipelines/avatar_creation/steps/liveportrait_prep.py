"""Stage 7: derive the avatar's driving clip (motion profile) from its upload.

LivePortrait is driving-based — it replays motion from a driving video rather than
learning a per-person motion model. So the avatar's "motion profile" is a short,
frontal, stable window cut from the user's own uploaded video; at generation time
it is palindrome-looped to the speech length and used as the driving input.
"""

from __future__ import annotations

from pathlib import Path

from app.pipelines.avatar_creation.ml.backends import AvatarBackend


def prep_driving(backend: AvatarBackend, *, source_video: Path, out_driving: Path) -> dict:
    """Produce driving.mp4 from the uploaded video. Returns {path, model, ...}."""
    return backend.prep_driving(source_video, out_driving)
