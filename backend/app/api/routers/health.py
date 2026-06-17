"""Healthcheck endpoint — verifies the process is up and the DB is reachable."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/healthcheck")
def healthcheck(db: Session = Depends(get_db)) -> dict[str, str]:
    """Liveness + DB readiness probe."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # pragma: no cover - defensive
        db_status = "error"
    return {"status": "ok", "version": __version__, "db": db_status}
