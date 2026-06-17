"""Backend selection for the avatar-creation pipeline.

The real backend runs ML in isolated micromamba envs via subprocess (see
ml/backends.py + _subproc.py), so there are no in-process model loaders here any
more — just the cached backend selector.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.pipelines.avatar_creation.ml.backends import (
    AvatarBackend,
    RealBackend,
    StubBackend,
)

logger = get_logger("pipeline.loaders")


@lru_cache(maxsize=1)
def get_backend() -> AvatarBackend:
    """Return the configured avatar pipeline backend (cached)."""
    choice = settings.PIPELINE_BACKEND.lower()
    if choice == "stub":
        backend: AvatarBackend = StubBackend()
    elif choice == "real":
        backend = RealBackend()
    else:  # auto
        backend = RealBackend() if RealBackend.is_available() else StubBackend()
    logger.info("Avatar pipeline backend: %s", backend.name)
    return backend
