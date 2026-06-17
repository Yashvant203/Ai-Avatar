"""FastAPI application factory.

Run locally:  uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.router import api_router
from app.api.routers import health
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

logger = get_logger("app")


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title="AI Avatar Platform API",
        version=__version__,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Root-level healthcheck (per spec) + the same router under /api.
    app.include_router(health.router)
    app.include_router(api_router, prefix="/api")

    # Optionally serve the built Next.js static export same-origin (deployment).
    # API + healthcheck are registered above, so they take precedence; the SPA
    # mount at "/" is a fallback for all other paths.
    if settings.FRONTEND_DIST is not None:
        dist = settings.FRONTEND_DIST
        if dist.is_dir():
            from fastapi.staticfiles import StaticFiles

            app.mount("/", StaticFiles(directory=str(dist), html=True), name="frontend")
            logger.info("Serving frontend from %s", dist)
        else:
            logger.warning("FRONTEND_DIST set but not found: %s", dist)

    logger.info("App initialized (env=%s, version=%s)", settings.ENV, __version__)
    return app


app = create_app()
