from __future__ import annotations

from sqlalchemy.orm import Session

from server.app.models.user import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    normalized = str(username or "").strip()
    if not normalized:
        return None
    return db.query(User).filter(User.username == normalized).first()

