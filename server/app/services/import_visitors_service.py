# Purpose: Import visitor profiles and auto-provision missing visitor users securely.
# Workflow Role: Supports back-office setup with safe temporary credential handling.

from __future__ import annotations

import secrets
import string
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from server.app.auth.password import hash_password
from server.app.enums.roles import UserRole
from server.app.errors import err
from server.app.models.user import User
from server.app.models.visitor_profile import VisitorProfile

REQUIRED_VISITOR_COLUMNS = {
    "username",
    "role",
    "visitor_code",
    "full_name",
    "default_start_lat",
    "default_start_lon",
    "default_capacity",
    "is_active",
}


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%*_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


# Read visitor profile data from an Excel file
# Contract: read_visitor_excel executes one deterministic step in the workflow.
def read_visitor_excel(file_path: str | Path) -> pd.DataFrame:
    return pd.read_excel(file_path)


# Normalize Excel column names
# Contract: normalize_column_names executes one deterministic step in the workflow.
def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(col).strip().lower() for col in normalized.columns]
    return normalized


# Validate required visitor columns
# Contract: validate_visitor_columns executes one deterministic step in the workflow.
def validate_visitor_columns(df: pd.DataFrame) -> None:
    missing_columns = set(REQUIRED_VISITOR_COLUMNS) - set(df.columns)
    if missing_columns:
        missing_str = ", ".join(sorted(missing_columns))
        raise ValueError(err("missing_required_columns", columns=missing_str))


# Contract: normalize_bool_value executes one deterministic step in the workflow.
def normalize_bool_value(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    value = str(value).strip().lower()
    return value in {"true", "1", "t", "y", "yes"}


# Clean and normalize visitor data
# Contract: transform_visitor_dataframe executes one deterministic step in the workflow.
def transform_visitor_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized["username"] = normalized["username"].astype(str).str.strip()
    normalized["role"] = normalized["role"].astype(str).str.strip().str.lower()
    normalized["visitor_code"] = normalized["visitor_code"].astype(str).str.strip()
    normalized["full_name"] = normalized["full_name"].astype(str).str.strip()
    normalized["default_start_lat"] = pd.to_numeric(normalized["default_start_lat"], errors="coerce")
    normalized["default_start_lon"] = pd.to_numeric(normalized["default_start_lon"], errors="coerce")
    normalized["default_capacity"] = (
        pd.to_numeric(normalized["default_capacity"], errors="coerce").fillna(30).astype(int)
    )
    normalized["is_active"] = normalized["is_active"].apply(normalize_bool_value)

    # FIX: [SEC-01] Optional temp_password input; if absent per-row password will be generated.
    if "temp_password" not in normalized.columns:
        normalized["temp_password"] = None
    normalized["temp_password"] = normalized["temp_password"].apply(
        lambda v: str(v).strip() if pd.notna(v) and str(v).strip() else None
    )
    return normalized


# Contract: validate_visitor_values executes one deterministic step in the workflow.
def validate_visitor_values(df: pd.DataFrame) -> None:
    required_non_empty = ["username", "role", "visitor_code", "full_name"]
    for column_name in required_non_empty:
        if (df[column_name] == "").any():
            raise ValueError(f"ستون {column_name} نمی‌تواند خالی باشد.")

    duplicate_visitor_codes = df[df["visitor_code"].duplicated()]["visitor_code"].tolist()
    if duplicate_visitor_codes:
        duplicate_str = ", ".join(sorted(set(duplicate_visitor_codes)))
        raise ValueError(f"کد ویزیتور تکراری در فایل وجود دارد: {duplicate_str}")

    duplicate_usernames = df[df["username"].duplicated()]["username"].tolist()
    if duplicate_usernames:
        duplicate_str = ", ".join(sorted(set(duplicate_usernames)))
        raise ValueError(f"نام کاربری تکراری در فایل وجود دارد: {duplicate_str}")

    valid_roles = {role.value for role in UserRole}
    invalid_roles = sorted(set(df["role"]) - valid_roles)
    if invalid_roles:
        invalid_str = ", ".join(invalid_roles)
        raise ValueError(f"نقش نامعتبر در فایل وجود دارد: {invalid_str}")

    non_visitor_roles = sorted(set(df[df["role"] != UserRole.VISITOR.value]["role"]))
    if non_visitor_roles:
        non_visitor_str = ", ".join(non_visitor_roles)
        raise ValueError(f"در این فایل فقط role=visitor مجاز است. مقادیر نامعتبر: {non_visitor_str}")


def resolve_or_create_visitor_user(
    row: pd.Series,
    db: Session,
    generated_passwords: dict[str, str],
) -> User:
    existing_user = (
        db.query(User)
        .filter(User.username == row["username"])
        .first()
    )

    if existing_user:
        if existing_user.role != UserRole.VISITOR.value:
            raise ValueError(
                f"کاربر «{row['username']}» با نقش «{existing_user.role}» وجود دارد و قابل استفاده برای visitor نیست."
            )
        existing_user.is_active = bool(row["is_active"])
        if row.get("temp_password"):
            existing_user.password_hash = hash_password(str(row["temp_password"]))
            existing_user.must_change_password = True
        return existing_user

    temp_password = str(row.get("temp_password") or _generate_temp_password())
    if not row.get("temp_password"):
        generated_passwords[str(row["username"])] = temp_password

    new_user = User(
        username=row["username"],
        password_hash=hash_password(temp_password),
        role=UserRole.VISITOR.value,
        is_active=bool(row["is_active"]),
        must_change_password=True,
    )
    db.add(new_user)
    db.flush()
    return new_user


# Insert new visitor profiles or update existing ones based on visitor_code
# Contract: upsert_visitor_profiles executes one deterministic step in the workflow.
def upsert_visitor_profiles(df: pd.DataFrame, db: Session) -> dict:
    processed_count = 0
    generated_passwords: dict[str, str] = {}
    try:
        for _, row in df.iterrows():
            linked_user = resolve_or_create_visitor_user(row, db, generated_passwords)

            existing_profile = (
                db.query(VisitorProfile)
                .filter(VisitorProfile.visitor_code == row["visitor_code"])
                .first()
            )

            if existing_profile:
                if existing_profile.user_id != linked_user.id:
                    raise ValueError(
                        f"تداخل visitor_code «{row['visitor_code']}»: قبلاً به کاربر دیگری متصل است."
                    )
                existing_profile.full_name = row["full_name"]
                existing_profile.default_start_lat = row["default_start_lat"]
                existing_profile.default_start_lon = row["default_start_lon"]
                existing_profile.default_capacity = int(row["default_capacity"])
                existing_profile.is_active = bool(row["is_active"])
            else:
                existing_profile_for_user = (
                    db.query(VisitorProfile)
                    .filter(VisitorProfile.user_id == linked_user.id)
                    .first()
                )
                if existing_profile_for_user:
                    raise ValueError(
                        f"تداخل username «{row['username']}»: کاربر قبلاً به visitor_code دیگری متصل است."
                    )

                new_profile = VisitorProfile(
                    user_id=linked_user.id,
                    visitor_code=row["visitor_code"],
                    full_name=row["full_name"],
                    default_start_lat=row["default_start_lat"],
                    default_start_lon=row["default_start_lon"],
                    default_capacity=int(row["default_capacity"]),
                    is_active=bool(row["is_active"]),
                )
                db.add(new_profile)

            processed_count += 1

        db.commit()
        return {
            "processed_count": int(processed_count),
            "generated_temp_passwords": generated_passwords,
        }
    except Exception:
        db.rollback()
        raise


# Full import flow for visitor profiles
# Contract: import_visitor_profiles_from_excel executes one deterministic step in the workflow.
def import_visitor_profiles_from_excel(file_path: str | Path, db: Session) -> dict:
    df = read_visitor_excel(file_path)
    df = normalize_column_names(df)
    validate_visitor_columns(df)
    df = transform_visitor_dataframe(df)
    validate_visitor_values(df)
    return upsert_visitor_profiles(df, db)

