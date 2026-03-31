from sqlalchemy.orm import Session

from server.app.auth.password import verify_password
from server.app.models.user import User


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    normalized_username = str(username or "").strip()
    if not normalized_username:
        return None

    user = (
        db.query(User)
        .filter(User.username == normalized_username)
        .first()
    )
    if not user:
        return None
    if not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None

    return user


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def require_roles(user_role: str, allowed_roles: list[str] | set[str] | tuple[str, ...]) -> None:
    if user_role not in allowed_roles:
        raise PermissionError("You are not authorized to access this page.")
