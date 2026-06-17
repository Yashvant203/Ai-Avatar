"""Authentication business logic: signup, authenticate, token refresh rotation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import TokenPair


class AuthError(Exception):
    """Domain error for auth failures (mapped to HTTP 4xx in the router)."""

    def __init__(self, message: str, *, code: str = "auth_error") -> None:
        super().__init__(message)
        self.code = code


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email.lower()))


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.get(User, user_id)


def signup(db: Session, *, email: str, password: str, full_name: str | None) -> User:
    email = email.lower()
    if get_user_by_email(db, email) is not None:
        raise AuthError("Email already registered", code="email_taken")

    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=full_name,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, *, email: str, password: str) -> User:
    user = get_user_by_email(db, email)
    # Verify even when the user is missing to reduce timing-based user enumeration.
    if user is None:
        hash_password(password)  # burn comparable time
        raise AuthError("Invalid email or password", code="bad_credentials")
    if not verify_password(password, user.hashed_password):
        raise AuthError("Invalid email or password", code="bad_credentials")
    if not user.is_active:
        raise AuthError("Account is disabled", code="inactive")

    # Opportunistically upgrade the hash if argon2 params changed.
    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(password)
        db.commit()
    return user


def issue_tokens(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


def refresh_tokens(db: Session, *, refresh_token: str) -> TokenPair:
    """Validate a refresh token and rotate it (issue a fresh pair)."""
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise AuthError("Invalid refresh token", code="bad_token") from exc

    user = get_user_by_id(db, int(payload["sub"]))
    if user is None or not user.is_active:
        raise AuthError("User no longer valid", code="bad_token")

    # Stateless rotation: a new refresh token is minted on every refresh. A
    # server-side revocation/denylist can be layered in later (see roadmap risk).
    return issue_tokens(user)
