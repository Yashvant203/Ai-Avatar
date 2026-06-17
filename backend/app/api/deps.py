"""Shared FastAPI dependencies: current-user resolution and a rate-limit stub."""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_token
from app.db.session import get_db
from app.models.user import User
from app.services import auth_service

_bearer = HTTPBearer(auto_error=False)

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the User from a Bearer access token, or raise 401."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise _CREDENTIALS_EXC
    try:
        payload = decode_token(creds.credentials, expected_type="access")
    except TokenError as exc:
        raise _CREDENTIALS_EXC from exc

    user = auth_service.get_user_by_id(db, int(payload["sub"]))
    if user is None:
        raise _CREDENTIALS_EXC
    return user


def get_current_active_user(user: User = Depends(get_current_user)) -> User:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive account")
    return user


# --- Rate-limit stub -------------------------------------------------------
# A minimal in-memory fixed-window limiter for auth endpoints. This is a STUB:
# it is per-process only (no good behind multiple workers) and should be
# replaced with a shared store (Redis) or a reverse-proxy limit before prod.
class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "anon"
        now = time.monotonic()
        recent = [t for t in self._hits[key] if now - t < self.window]
        if len(recent) >= self.max:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, slow down.",
            )
        recent.append(now)
        self._hits[key] = recent


# 10 attempts per minute per IP on sensitive auth routes.
auth_rate_limit = RateLimiter(max_requests=10, window_seconds=60)
