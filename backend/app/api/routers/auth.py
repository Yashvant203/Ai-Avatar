"""Authentication routes: signup, login, refresh, me."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import auth_rate_limit, get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    UserOut,
)
from app.services import auth_service
from app.services.auth_service import AuthError

router = APIRouter()

_ERROR_STATUS = {
    "email_taken": status.HTTP_409_CONFLICT,
    "bad_credentials": status.HTTP_401_UNAUTHORIZED,
    "inactive": status.HTTP_403_FORBIDDEN,
    "bad_token": status.HTTP_401_UNAUTHORIZED,
}


def _http_error(exc: AuthError) -> HTTPException:
    return HTTPException(
        status_code=_ERROR_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST),
        detail=str(exc),
    )


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    db: Session = Depends(get_db),
    _: None = Depends(auth_rate_limit),
) -> TokenPair:
    try:
        user = auth_service.signup(
            db, email=body.email, password=body.password, full_name=body.full_name
        )
    except AuthError as exc:
        raise _http_error(exc) from exc
    return auth_service.issue_tokens(user)


@router.post("/login", response_model=TokenPair)
def login(
    body: LoginRequest,
    db: Session = Depends(get_db),
    _: None = Depends(auth_rate_limit),
) -> TokenPair:
    try:
        user = auth_service.authenticate(db, email=body.email, password=body.password)
    except AuthError as exc:
        raise _http_error(exc) from exc
    return auth_service.issue_tokens(user)


@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        return auth_service.refresh_tokens(db, refresh_token=body.refresh_token)
    except AuthError as exc:
        raise _http_error(exc) from exc


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_active_user)) -> User:
    return current_user
