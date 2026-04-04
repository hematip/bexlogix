# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from server.app.errors import err
from server.app.auth.password import hash_password, verify_password
from server.app.enums.roles import UserRole
from server.app.models.user import User

REQUIRED_USER_COLUMNS = {
    "username",
    "password",
    "role",
    "is_active",
}


# Read user seed data from an Excel file
# Contract: read_user_excel executes one deterministic step in the workflow.
def read_user_excel(file_path: str | Path) -> pd.DataFrame:
    return pd.read_excel(file_path)


# Normalize Excel column names
# Contract: normalize_column_names executes one deterministic step in the workflow.
def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


# Validate required user columns
# Contract: validate_user_columns executes one deterministic step in the workflow.
def validate_user_columns(df: pd.DataFrame) -> None:
    missing_columns = set(REQUIRED_USER_COLUMNS) - set(df.columns)
    if missing_columns:
        missing_str = ", ".join(sorted(missing_columns))
        raise ValueError(err("missing_required_columns", columns=missing_str))


# Convert Excel-like boolean values to Python bool
# Contract: normalize_bool_value executes one deterministic step in the workflow.
def normalize_bool_value(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    value = str(value).strip().lower()
    return value in {"true", "1", "t", "y", "yes"}


# Clean and normalize user seed data
# Contract: transform_user_dataframe executes one deterministic step in the workflow.
def transform_user_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["username"] = df["username"].astype(str).str.strip()
    df["password"] = df["password"].astype(str).str.strip()
    df["role"] = df["role"].astype(str).str.strip().str.lower()
    df["is_active"] = df["is_active"].apply(normalize_bool_value)
    return df


# Contract: validate_user_values executes one deterministic step in the workflow.
def validate_user_values(df: pd.DataFrame) -> None:
    if (df["username"] == "").any():
        raise ValueError("نام کاربری نمی‌تواند خالی باشد.")

    if (df["password"] == "").any():
        raise ValueError("رمز عبور نمی‌تواند خالی باشد.")

    duplicate_usernames = df[df["username"].duplicated()]["username"].tolist()
    if duplicate_usernames:
        duplicate_str = ", ".join(sorted(set(duplicate_usernames)))
        raise ValueError(f"نام‌های کاربری تکراری در فایل وجود دارد: {duplicate_str}")

    valid_roles = {role.value for role in UserRole}
    invalid_roles = sorted(set(df["role"]) - valid_roles)
    if invalid_roles:
        invalid_str = ", ".join(invalid_roles)
        raise ValueError(f"نقش‌های نامعتبر در فایل یافت شد: {invalid_str}")


# Insert new users or update existing users based on username
# Password is always stored as hash
# Contract: upsert_users executes one deterministic step in the workflow.
def upsert_users(df: pd.DataFrame, db: Session) -> int:
    processed_count = 0
    try:
        for _, row in df.iterrows():
            username = row["username"]
            incoming_password = row["password"]
            role = row["role"]
            is_active = bool(row["is_active"])

            existing_user = (
                db.query(User)
                .filter(User.username == username)
                .first()
            )

            if existing_user:
                existing_user.role = role
                existing_user.is_active = is_active
                existing_user.must_change_password = False

                # Re-hash only when incoming plain password does not match existing hash.
                if not verify_password(incoming_password, existing_user.password_hash):
                    existing_user.password_hash = hash_password(incoming_password)
            else:
                new_user = User(
                    username=username,
                    password_hash=hash_password(incoming_password),
                    role=role,
                    is_active=is_active,
                    must_change_password=False,
                )
                db.add(new_user)

            processed_count += 1

        db.commit()
        return processed_count
    except Exception:
        db.rollback()
        raise


# Full import flow for user seed data
# Contract: import_users_from_excel executes one deterministic step in the workflow.
def import_users_from_excel(file_path: str | Path, db: Session) -> int:
    df = read_user_excel(file_path)
    df = normalize_column_names(df)
    validate_user_columns(df)
    df = transform_user_dataframe(df)
    validate_user_values(df)
    return upsert_users(df, db)
