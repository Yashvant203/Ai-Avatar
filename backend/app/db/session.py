"""Database engine, session factory, and FastAPI dependency.

For SQLite we enable WAL mode and enforce foreign keys via a connect-time
PRAGMA hook (SQLite has FKs off by default). See DATABASE_SCHEMA.md and
SYSTEM_ARCHITECTURE.md for the concurrency rationale.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

engine: Engine = create_engine(
    settings.DATABASE_URL,
    # SQLite + multithreaded FastAPI needs this flag.
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    future=True,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
    """Enable WAL + foreign key enforcement on every SQLite connection."""
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
