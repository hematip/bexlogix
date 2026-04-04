# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from sqlalchemy.orm import Session

from server.app.models.user import User


# Contract: get_user_by_id executes one deterministic step in the workflow.
def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


# Contract: get_user_by_username executes one deterministic step in the workflow.
def get_user_by_username(db: Session, username: str) -> User | None:
    normalized = str(username or "").strip()
    if not normalized:
        return None
    return db.query(User).filter(User.username == normalized).first()

