"""Pytest fixtures: an isolated in-memory SQLite DB and a TestClient with the
get_db dependency overridden.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app


def _enable_sqlite_fks(engine) -> None:
    """Mirror production: enforce ON DELETE CASCADE / SET NULL in tests."""

    @event.listens_for(engine, "connect")
    def _set_fk(dbapi_connection, _record):  # noqa: ANN001
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    # Single shared in-memory connection across the test (StaticPool).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _enable_sqlite_fks(engine)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture(autouse=True)
def tmp_storage(tmp_path, monkeypatch) -> None:
    """Redirect all storage path builders to an isolated tmp dir per test."""
    import app.core.paths as paths

    monkeypatch.setattr(paths, "STORAGE_ROOT", tmp_path.resolve())


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> Generator[None, None, None]:
    """Clear the per-process auth rate-limiter so test order can't trip 429s."""
    from app.api.deps import auth_rate_limit

    auth_rate_limit._hits.clear()
    yield
    auth_rate_limit._hits.clear()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
