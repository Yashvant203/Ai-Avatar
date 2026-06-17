"""Stage 7: prepare the LivePortrait appearance/motion template from the face crop."""

from __future__ import annotations

from pathlib import Path

from app.pipelines.avatar_creation.ml.backends import AvatarBackend


def prep_appearance(backend: AvatarBackend, *, face: Path, out_template: Path) -> dict:
    """Produce motion_template.pkl from face.png. Returns {path, model}."""
    return backend.prep_appearance(face, out_template)
