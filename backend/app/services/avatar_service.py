"""Owner-scoped avatar CRUD helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.avatar import Avatar
from app.models.enums import AvatarStatus


class AvatarNotFound(Exception):
    """Raised when an avatar does not exist or is not owned by the caller."""


def create_avatar(db: Session, *, user_id: int, name: str) -> Avatar:
    avatar = Avatar(user_id=user_id, name=name, status=AvatarStatus.pending)
    db.add(avatar)
    db.commit()
    db.refresh(avatar)
    return avatar


def list_avatars(db: Session, *, user_id: int) -> list[Avatar]:
    return list(
        db.scalars(
            select(Avatar).where(Avatar.user_id == user_id).order_by(Avatar.created_at.desc())
        )
    )


def get_owned_avatar(db: Session, *, user_id: int, avatar_id: int) -> Avatar:
    """Fetch an avatar scoped to its owner, or raise AvatarNotFound.

    Scoping by user_id here is the authorization boundary — a user can never
    read or mutate another user's avatar, and we return 404 (not 403) to avoid
    leaking existence.
    """
    avatar = db.scalar(select(Avatar).where(Avatar.id == avatar_id, Avatar.user_id == user_id))
    if avatar is None:
        raise AvatarNotFound(f"avatar {avatar_id} not found")
    return avatar


def delete_avatar(db: Session, *, user_id: int, avatar_id: int) -> None:
    avatar = get_owned_avatar(db, user_id=user_id, avatar_id=avatar_id)
    db.delete(avatar)
    db.commit()
