from passlib.context import CryptContext

_password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    plain_password = str(plain_password or "").strip()
    if not plain_password:
        raise ValueError("Password cannot be empty.")
    return _password_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_password = str(plain_password or "").strip()
    hashed_password = str(hashed_password or "").strip()

    if not plain_password or not hashed_password:
        return False

    try:
        return _password_context.verify(plain_password, hashed_password)
    except (ValueError, TypeError):
        return False
