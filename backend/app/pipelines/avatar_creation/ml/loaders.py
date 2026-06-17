"""Lazy, cached model loaders + backend selection.

Real model instances (insightface, LivePortrait) are expensive to construct, so
they are created once and shared across jobs. On a single GPU this keeps weights
warm between avatar creations (see SYSTEM_ARCHITECTURE.md, AI pipeline section).
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


@lru_cache(maxsize=1)
def get_face_analyzer():  # pragma: no cover - requires ML stack
    """Lazily construct and cache the insightface analyzer."""
    from insightface.app import FaceAnalysis

    app = FaceAnalysis(name="buffalo_l")
    app.prepare(ctx_id=0, det_size=(640, 640))
    return app


@lru_cache(maxsize=1)
def get_liveportrait():  # pragma: no cover - requires ML stack
    """Lazily construct and cache the LivePortrait pipeline.

    Placeholder loader — wire to the real LivePortrait entrypoint and the weights
    under ml_models/weights/liveportrait/ when integrating the model.
    """
    raise NotImplementedError(
        "LivePortrait integration pending — see AVATAR_CREATION_PIPELINE.md §7"
    )
