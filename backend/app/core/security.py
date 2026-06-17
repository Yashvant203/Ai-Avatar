"""Password hashing (argon2) and JWT issue/verify (HS256).

Tokens carry `sub` (user id), `exp`, `iat`, and a `type` claim
("access" | "refresh") so a refresh token can never be used as an access token
and vice-versa. Refresh-token rotation is handled in the auth service.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

_ph = PasswordHasher()


# --- Password hashing ------------------------------------------------------
def hash_password(plain: str) -> str:
    """Return an argon2 hash for a plaintext password."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time-ish verification. Returns False on any mismatch/format error."""
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError, Exception):  # noqa: BLE001
        return False


def needs_rehash(hashed: str) -> bool:
    """True if the stored hash should be upgraded (params changed)."""
    try:
        return _ph.check_needs_rehash(hashed)
    except Exception:  # noqa: BLE001
        return False


# --- JWT -------------------------------------------------------------------
class TokenError(Exception):
    """Raised when a token is invalid, expired, or of the wrong type."""


def _create_token(subject: str | int, token_type: TokenType, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=ttl_seconds)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def create_access_token(subject: str | int) -> str:
    return _create_token(subject, "access", settings.ACCESS_TTL)


def create_refresh_token(subject: str | int) -> str:
    return _create_token(subject, "refresh", settings.REFRESH_TTL)


def decode_token(token: str, expected_type: TokenType) -> dict:
    """Decode and validate a JWT, enforcing signature, expiry, and `type`.

    Raises TokenError on any problem.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except JWTError as exc:
        raise TokenError("invalid or expired token") from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"expected {expected_type} token")
    if "sub" not in payload:
        raise TokenError("token missing subject")
    return payload
