"""Auth flow tests: signup, login, me, refresh rotation, and failure modes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

from app.core.config import settings

SIGNUP = {"email": "alice@example.com", "password": "s3cret-password", "full_name": "Alice"}


def _signup(client: TestClient, **overrides) -> dict:
    payload = {**SIGNUP, **overrides}
    return client.post("/api/auth/signup", json=payload)


def test_signup_returns_token_pair(client: TestClient) -> None:
    resp = _signup(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"


def test_signup_duplicate_email_conflicts(client: TestClient) -> None:
    assert _signup(client).status_code == 201
    dup = _signup(client)
    assert dup.status_code == 409


def test_login_and_me(client: TestClient) -> None:
    _signup(client)
    login = client.post(
        "/api/auth/login", json={"email": SIGNUP["email"], "password": SIGNUP["password"]}
    )
    assert login.status_code == 200
    access = login.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    assert me.json()["email"] == SIGNUP["email"]
    assert "hashed_password" not in me.json()


def test_login_wrong_password(client: TestClient) -> None:
    _signup(client)
    resp = client.post(
        "/api/auth/login", json={"email": SIGNUP["email"], "password": "wrong-password"}
    )
    assert resp.status_code == 401


def test_me_requires_token(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_expired_token(client: TestClient) -> None:
    expired = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "exp": int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()),
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALG,
    )
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_me_rejects_refresh_token_as_access(client: TestClient) -> None:
    refresh = _signup(client).json()["refresh_token"]
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh}"})
    assert resp.status_code == 401


def test_refresh_rotates_tokens(client: TestClient) -> None:
    refresh = _signup(client).json()["refresh_token"]
    resp = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"] and body["refresh_token"]

    # The new access token works against a protected route.
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


def test_refresh_rejects_invalid_token(client: TestClient) -> None:
    resp = client.post("/api/auth/refresh", json={"refresh_token": "not-a-jwt"})
    assert resp.status_code == 401
