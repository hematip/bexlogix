# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from passlib.context import CryptContext

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Contract: hash_password executes one deterministic step in the workflow.
def hash_password(plain_password: str) -> str:
    plain_password = str(plain_password or "").strip()
    if not plain_password:
        raise ValueError("رمز عبور نمی‌تواند خالی باشد.")
    return _password_context.hash(plain_password)


# Contract: verify_password executes one deterministic step in the workflow.
def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_password = str(plain_password or "").strip()
    hashed_password = str(hashed_password or "").strip()

    if not plain_password or not hashed_password:
        return False

    try:
        return _password_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False
