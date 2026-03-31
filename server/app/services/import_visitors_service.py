from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from server.app.auth.password import hash_password
from server.app.enums.roles import UserRole
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


# Read visitor profile data from an Excel file
def read_visitor_excel(file_path: str | Path) -> pd.DataFrame:
    return pd.read_excel(file_path)


# Normalize Excel column names
def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


# Validate required visitor columns
def validate_visitor_columns(df: pd.DataFrame) -> None:
    missing_columns = set(REQUIRED_VISITOR_COLUMNS) - set(df.columns)
    if missing_columns:
        missing_str = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns: {missing_str}")


def normalize_bool_value(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    value = str(value).strip().lower()
    return value in {"true", "1", "t", "y", "yes"}


# Clean and normalize visitor data
def transform_visitor_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["username"] = df["username"].astype(str).str.strip()
    df["role"] = df["role"].astype(str).str.strip().str.lower()
    df["visitor_code"] = df["visitor_code"].astype(str).str.strip()
    df["full_name"] = df["full_name"].astype(str).str.strip()
    df["default_start_lat"] = pd.to_numeric(df["default_start_lat"], errors="coerce")
    df["default_start_lon"] = pd.to_numeric(df["default_start_lon"], errors="coerce")
    df["default_capacity"] = pd.to_numeric(df["default_capacity"], errors="coerce").fillna(30).astype(int)
    df["is_active"] = df["is_active"].apply(normalize_bool_value)
    return df


def validate_visitor_values(df: pd.DataFrame) -> None:
    required_non_empty = ["username", "role", "visitor_code", "full_name"]
    for column_name in required_non_empty:
        if (df[column_name] == "").any():
            raise ValueError(f"{column_name} cannot be empty.")

    duplicate_visitor_codes = df[df["visitor_code"].duplicated()]["visitor_code"].tolist()
    if duplicate_visitor_codes:
        duplicate_str = ", ".join(sorted(set(duplicate_visitor_codes)))
        raise ValueError(f"Duplicate visitor_code values found in import file: {duplicate_str}")

    duplicate_usernames = df[df["username"].duplicated()]["username"].tolist()
    if duplicate_usernames:
        duplicate_str = ", ".join(sorted(set(duplicate_usernames)))
        raise ValueError(f"Duplicate username values found in import file: {duplicate_str}")

    valid_roles = {role.value for role in UserRole}
    invalid_roles = sorted(set(df["role"]) - valid_roles)
    if invalid_roles:
        invalid_str = ", ".join(invalid_roles)
        raise ValueError(f"Invalid role values: {invalid_str}")

    non_visitor_roles = sorted(set(df[df["role"] != UserRole.VISITOR.value]["role"]))
    if non_visitor_roles:
        non_visitor_str = ", ".join(non_visitor_roles)
        raise ValueError(f"Visitor import only accepts role='{UserRole.VISITOR.value}'. Found: {non_visitor_str}")


def resolve_or_create_visitor_user(row: pd.Series, db: Session) -> User:
    existing_user = (
        db.query(User)
        .filter(User.username == row["username"])
        .first()
    )

    if existing_user:
        if existing_user.role != UserRole.VISITOR.value:
            raise ValueError(
                f"User '{row['username']}' already exists with role '{existing_user.role}', "
                f"expected '{UserRole.VISITOR.value}'."
            )
        existing_user.is_active = bool(row["is_active"])
        return existing_user

    # MVP-only behavior:
    # Auto-create missing visitor users during visitor import.
    # This temporary flow will be replaced by explicit auth/user provisioning in a later phase.
    new_user = User(
        username=row["username"],
        password_hash=hash_password("change_me"),
        role=UserRole.VISITOR.value,
        is_active=bool(row["is_active"]),
    )
    db.add(new_user)
    db.flush()
    return new_user


# Insert new visitor profiles or update existing ones based on visitor_code
def upsert_visitor_profiles(df: pd.DataFrame, db: Session) -> int:
    processed_count = 0
    try:
        for _, row in df.iterrows():
            linked_user = resolve_or_create_visitor_user(row, db)

            existing_profile = (
                db.query(VisitorProfile)
                .filter(VisitorProfile.visitor_code == row["visitor_code"])
                .first()
            )

            if existing_profile:
                if existing_profile.user_id != linked_user.id:
                    raise ValueError(
                        f"Conflict for visitor_code '{row['visitor_code']}': "
                        f"already linked to user_id={existing_profile.user_id}, "
                        f"cannot link to user_id={linked_user.id}."
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
                        f"Conflict for username '{row['username']}': "
                        f"user already linked to visitor_code='{existing_profile_for_user.visitor_code}', "
                        f"cannot insert visitor_code='{row['visitor_code']}'."
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
        return processed_count
    except Exception:
        db.rollback()
        raise

# Full import flow for visitor profiles
def import_visitor_profiles_from_excel(file_path: str | Path, db: Session) -> int:
    df = read_visitor_excel(file_path)
    df = normalize_column_names(df)
    validate_visitor_columns(df)
    df = transform_visitor_dataframe(df)
    validate_visitor_values(df)
    return upsert_visitor_profiles(df, db)
