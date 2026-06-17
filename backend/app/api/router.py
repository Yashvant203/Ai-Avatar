"""Top-level /api router. Mount feature routers here as phases land."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routers import auth, avatars, generation, health

api_router = APIRouter()

# Health lives at the app root via main.py; also exposed under /api for uniformity.
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(avatars.router, prefix="/avatars", tags=["avatars"])
api_router.include_router(generation.router, tags=["generation"])
