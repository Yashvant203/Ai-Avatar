"""Smoke test for the healthcheck endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_healthcheck_ok() -> None:
    resp = client.get("/healthcheck")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "version" in body
