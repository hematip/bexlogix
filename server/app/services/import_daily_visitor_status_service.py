# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from server.app.errors import err
from server.app.enums.roles import UserRole
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.user import User
from server.app.models.visitor_profile import VisitorProfile

REQUIRED_DAILY_VISITOR_STATUS_COLUMNS = {
    "work_date",
    "username",
    "visitor_code",
    "full_name",
    "start_lat",
    "start_lon",
    "capacity",
    "is_active_today",
}


# Contract: read_daily_visitor_status_excel executes one deterministic step in the workflow.
def read_daily_visitor_status_excel(file_path: str | Path) -> pd.DataFrame:
    return pd.read_excel(file_path)


# Contract: normalize_column_names executes one deterministic step in the workflow.
def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    normalized_df = df.copy()
    normalized_df.columns = [str(col).strip().lower() for col in normalized_df.columns]
    return normalized_df


# Contract: validate_daily_visitor_status_columns executes one deterministic step in the workflow.
def validate_daily_visitor_status_columns(df: pd.DataFrame) -> None:
    missing_columns = set(REQUIRED_DAILY_VISITOR_STATUS_COLUMNS) - set(df.columns)
    if missing_columns:
        missing_str = ", ".join(sorted(missing_columns))
        raise ValueError(err("missing_required_columns", columns=missing_str))


# Contract: normalize_bool_value executes one deterministic step in the workflow.
def normalize_bool_value(value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "t", "y", "yes"}


# Contract: transform_daily_visitor_status_dataframe executes one deterministic step in the workflow.
def transform_daily_visitor_status_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    transformed = df.copy()
    transformed["work_date"] = pd.to_datetime(transformed["work_date"], errors="coerce").dt.date
    transformed["username"] = transformed["username"].astype(str).str.strip()
    transformed["visitor_code"] = transformed["visitor_code"].astype(str).str.strip()
    transformed["full_name"] = transformed["full_name"].astype(str).str.strip()
    transformed["start_lat"] = pd.to_numeric(transformed["start_lat"], errors="coerce")
    transformed["start_lon"] = pd.to_numeric(transformed["start_lon"], errors="coerce")
    transformed["capacity_numeric"] = pd.to_numeric(transformed["capacity"], errors="coerce")
    transformed["is_active_today"] = transformed["is_active_today"].apply(normalize_bool_value)
    return transformed


# Contract: _row_error_message executes one deterministic step in the workflow.
def _row_error_message(row_index: int, message: str) -> str:
    return f"ردیف {row_index + 2}: {message}"


# Contract: validate_daily_visitor_status_values executes one deterministic step in the workflow.
def validate_daily_visitor_status_values(df: pd.DataFrame, db: Session) -> None:
    errors: list[str] = []

    for field in ["username", "visitor_code", "full_name"]:
        empty_rows = df[df[field] == ""]
        for idx in empty_rows.index:
            errors.append(_row_error_message(idx, f"ستون {field} نباید خالی باشد."))

    invalid_date_rows = df[df["work_date"].isna()]
    for idx in invalid_date_rows.index:
        errors.append(_row_error_message(idx, "تاریخ کار نامعتبر است یا خالی است."))

    invalid_capacity_rows = df[df["capacity_numeric"].isna()]
    for idx in invalid_capacity_rows.index:
        errors.append(_row_error_message(idx, "ظرفیت باید عدد صحیح معتبر باشد."))

    non_integer_capacity_rows = df[
        (~df["capacity_numeric"].isna()) & ((df["capacity_numeric"] % 1) != 0)
    ]
    for idx in non_integer_capacity_rows.index:
        errors.append(_row_error_message(idx, "ظرفیت باید عدد صحیح باشد."))

    negative_capacity_rows = df[(~df["capacity_numeric"].isna()) & (df["capacity_numeric"] < 0)]
    for idx in negative_capacity_rows.index:
        errors.append(_row_error_message(idx, "ظرفیت نمی‌تواند منفی باشد."))

    half_missing_coordinates_rows = df[df["start_lat"].isna() ^ df["start_lon"].isna()]
    for idx in half_missing_coordinates_rows.index:
        errors.append(
            _row_error_message(
                idx,
                "مختصات شروع باید کامل باشد؛ هر دو ستون start_lat و start_lon را وارد کنید.",
            )
        )

    missing_coordinates_rows = df[df["start_lat"].isna() & df["start_lon"].isna()]
    for idx in missing_coordinates_rows.index:
        errors.append(
            _row_error_message(idx, "مختصات شروع برای مسیر روزانه الزامی است.")
        )

    duplicate_rows = df[df.duplicated(subset=["username", "visitor_code", "work_date"], keep=False)]
    for idx in duplicate_rows.index:
        errors.append(_row_error_message(idx, "رکورد تکراری (username, visitor_code, work_date) وجود دارد."))

    for visitor_code, group in df.groupby("visitor_code"):
        usernames = set(group["username"])
        if len(usernames) > 1:
            errors.append(
                f"کد ویزیتور «{visitor_code}» به چند نام کاربری نگاشت شده است: {sorted(usernames)}"
            )

    for username, group in df.groupby("username"):
        visitor_codes = set(group["visitor_code"])
        if len(visitor_codes) > 1:
            errors.append(
                f"نام کاربری «{username}» به چند visitor_code نگاشت شده است: {sorted(visitor_codes)}"
            )

    usernames = set(df["username"].tolist())
    user_rows = (
        db.query(User.id, User.username, User.role)
        .filter(User.username.in_(usernames))
        .all()
    )
    users_by_username = {username: (user_id, role) for user_id, username, role in user_rows}

    unknown_usernames = sorted(usernames - set(users_by_username.keys()))
    if unknown_usernames:
        errors.append(err("unknown_usernames", usernames=", ".join(unknown_usernames)))

    invalid_role_usernames = sorted(
        username
        for username, (_, role) in users_by_username.items()
        if role != UserRole.VISITOR.value
    )
    if invalid_role_usernames:
        errors.append(err("daily_role_must_be_visitor", usernames=", ".join(invalid_role_usernames)))

    if errors:
        raise ValueError("\n".join(sorted(set(errors))))


# Contract: _resolve_target_profile executes one deterministic step in the workflow.
def _resolve_target_profile(
    db: Session,
    row: pd.Series,
    users_by_username: dict[str, User],
    profiles_by_code: dict[str, VisitorProfile],
    profiles_by_user_id: dict[int, VisitorProfile],
) -> VisitorProfile:
    username = row["username"]
    visitor_code = row["visitor_code"]
    full_name = row["full_name"]
    start_lat = float(row["start_lat"])
    start_lon = float(row["start_lon"])
    capacity = int(row["capacity_numeric"])
    is_active_today = bool(row["is_active_today"])

    user = users_by_username[username]
    profile_by_code = profiles_by_code.get(visitor_code)
    profile_by_user = profiles_by_user_id.get(user.id)

    if profile_by_code and profile_by_user and profile_by_code.id != profile_by_user.id:
        raise ValueError(
            f"تداخل نگاشت برای username='{username}' و visitor_code='{visitor_code}' وجود دارد."
        )

    target_profile = profile_by_code or profile_by_user
    if target_profile is None:
        target_profile = VisitorProfile(
            user_id=user.id,
            visitor_code=visitor_code,
            full_name=full_name,
            default_start_lat=start_lat,
            default_start_lon=start_lon,
            default_capacity=capacity,
            is_active=is_active_today,
        )
        db.add(target_profile)
        db.flush()
    else:
        target_profile.user_id = user.id
        target_profile.visitor_code = visitor_code
        target_profile.full_name = full_name
        target_profile.default_start_lat = start_lat
        target_profile.default_start_lon = start_lon
        target_profile.default_capacity = capacity
        target_profile.is_active = is_active_today

    profiles_by_code[target_profile.visitor_code] = target_profile
    profiles_by_user_id[target_profile.user_id] = target_profile
    return target_profile


# Contract: upsert_daily_visitor_statuses executes one deterministic step in the workflow.
def upsert_daily_visitor_statuses(df: pd.DataFrame, db: Session) -> int:
    users = (
        db.query(User)
        .filter(User.username.in_(set(df["username"].tolist())))
        .all()
    )
    users_by_username = {user.username: user for user in users}

    profiles = db.query(VisitorProfile).all()
    profiles_by_code = {profile.visitor_code: profile for profile in profiles}
    profiles_by_user_id = {profile.user_id: profile for profile in profiles}

    processed_count = 0
    try:
        for _, row in df.iterrows():
            target_profile = _resolve_target_profile(
                db=db,
                row=row,
                users_by_username=users_by_username,
                profiles_by_code=profiles_by_code,
                profiles_by_user_id=profiles_by_user_id,
            )

            work_date: date = row["work_date"]
            start_lat = float(row["start_lat"])
            start_lon = float(row["start_lon"])
            capacity_value = int(row["capacity_numeric"])
            is_active_today = bool(row["is_active_today"])

            existing_status = (
                db.query(DailyVisitorStatus)
                .filter(
                    DailyVisitorStatus.visitor_id == target_profile.id,
                    DailyVisitorStatus.work_date == work_date,
                )
                .first()
            )

            if existing_status:
                existing_status.start_lat = start_lat
                existing_status.start_lon = start_lon
                existing_status.capacity = capacity_value
                existing_status.is_active_today = is_active_today
            else:
                db.add(
                    DailyVisitorStatus(
                        visitor_id=target_profile.id,
                        work_date=work_date,
                        start_lat=start_lat,
                        start_lon=start_lon,
                        capacity=capacity_value,
                        is_active_today=is_active_today,
                    )
                )

            processed_count += 1

        db.commit()
        return processed_count
    except Exception:
        db.rollback()
        raise


# Contract: import_daily_visitor_statuses_from_excel executes one deterministic step in the workflow.
def import_daily_visitor_statuses_from_excel(file_path: str | Path, db: Session) -> int:
    df = read_daily_visitor_status_excel(file_path)
    df = normalize_column_names(df)
    validate_daily_visitor_status_columns(df)
    df = transform_daily_visitor_status_dataframe(df)
    validate_daily_visitor_status_values(df, db)
    return upsert_daily_visitor_statuses(df, db)
