"""Generation backend selection (cached). Mirrors avatar_creation.ml.loaders."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.pipelines.generation.ml.backends import (
    GenerationBackend,
    RealBackend,
    StubBackend,
)

logger = get_logger("generation.loaders")


@lru_cache(maxsize=1)
def get_generation_backend() -> GenerationBackend:
    choice = settings.PIPELINE_BACKEND.lower()
    if choice == "stub":
        backend: GenerationBackend = StubBackend()
    elif choice == "real":
        backend = RealBackend()
    else:  # auto
        backend = RealBackend() if RealBackend.is_available() else StubBackend()
    logger.info("Generation backend: %s", backend.name)
    return backend
