# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from sqlalchemy.orm import Session

from server.app.auth.password import hash_password, verify_password
from server.app.models.user import User


# Contract: authenticate_user executes one deterministic step in the workflow.
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


# Contract: get_user_by_id executes one deterministic step in the workflow.
def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


# Contract: require_roles executes one deterministic step in the workflow.
def require_roles(user_role: str, allowed_roles: list[str] | set[str] | tuple[str, ...]) -> None:
    if user_role not in allowed_roles:
        raise PermissionError("شما دسترسی لازم برای مشاهده این صفحه را ندارید.")


def change_password(
    db: Session,
    user_id: int,
    current_password: str,
    new_password: str,
) -> None:
    # FIX: [SEC-01] Centralized password change flow for must_change_password users.
    user = get_user_by_id(db=db, user_id=user_id)
    if not user or not user.is_active:
        raise ValueError("حساب کاربری معتبر نیست یا غیرفعال شده است.")

    if not verify_password(current_password, user.password_hash):
        raise ValueError("رمز عبور فعلی صحیح نیست.")

    normalized_new = str(new_password or "").strip()
    if len(normalized_new) < 8:
        raise ValueError("رمز عبور جدید باید حداقل ۸ کاراکتر باشد.")

    user.password_hash = hash_password(normalized_new)
    user.must_change_password = False
    db.commit()
