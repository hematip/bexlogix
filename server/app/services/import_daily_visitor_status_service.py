from datetime import date
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.visitor_profile import VisitorProfile

REQUIRED_DAILY_VISITOR_STATUS_COLUMNS = {
    "work_date",
    "visitor_code",
    "start_lat",
    "start_lon",
    "capacity",
    "is_active_today",
}


def read_daily_visitor_status_excel(file_path: str | Path) -> pd.DataFrame:
    return pd.read_excel(file_path)


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lower() for col in df.columns]
    return df


def validate_daily_visitor_status_columns(df: pd.DataFrame) -> None:
    missing_columns = set(REQUIRED_DAILY_VISITOR_STATUS_COLUMNS) - set(df.columns)
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


def transform_daily_visitor_status_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["visitor_code"] = df["visitor_code"].astype(str).str.strip()
    df["work_date"] = pd.to_datetime(df["work_date"], errors="coerce").dt.date
    df["start_lat"] = pd.to_numeric(df["start_lat"], errors="coerce")
    df["start_lon"] = pd.to_numeric(df["start_lon"], errors="coerce")
    df["capacity_numeric"] = pd.to_numeric(df["capacity"], errors="coerce")
    df["is_active_today"] = df["is_active_today"].apply(normalize_bool_value)
    return df


def _row_error_message(row_index: int, message: str) -> str:
    # +2 because DataFrame index is zero-based and Excel header is row 1.
    return f"Row {row_index + 2}: {message}"


def validate_daily_visitor_status_values(df: pd.DataFrame, db: Session) -> None:
    errors: list[str] = []

    empty_codes = df[df["visitor_code"] == ""]
    for idx in empty_codes.index:
        errors.append(_row_error_message(idx, "visitor_code cannot be empty."))

    invalid_date_rows = df[df["work_date"].isna()]
    for idx in invalid_date_rows.index:
        errors.append(_row_error_message(idx, "work_date is invalid or empty."))

    invalid_capacity_rows = df[df["capacity_numeric"].isna()]
    for idx in invalid_capacity_rows.index:
        errors.append(_row_error_message(idx, "capacity must be a valid integer number."))

    non_integer_capacity_rows = df[
        (~df["capacity_numeric"].isna()) & ((df["capacity_numeric"] % 1) != 0)
    ]
    for idx in non_integer_capacity_rows.index:
        errors.append(_row_error_message(idx, "capacity must be an integer value."))

    negative_capacity_rows = df[(~df["capacity_numeric"].isna()) & (df["capacity_numeric"] < 0)]
    for idx in negative_capacity_rows.index:
        errors.append(_row_error_message(idx, "capacity cannot be negative."))

    half_missing_coordinates_rows = df[
        df["start_lat"].isna() ^ df["start_lon"].isna()
    ]
    for idx in half_missing_coordinates_rows.index:
        errors.append(
            _row_error_message(
                idx,
                "start_lat and start_lon must both be present or both be empty.",
            )
        )

    duplicate_pairs = df[df.duplicated(subset=["visitor_code", "work_date"], keep=False)]
    for idx in duplicate_pairs.index:
        errors.append(
            _row_error_message(
                idx,
                "duplicate (visitor_code, work_date) found in file.",
            )
        )

    visitor_codes = set(df["visitor_code"].dropna().tolist())
    profile_rows = (
        db.query(
            VisitorProfile.visitor_code,
            VisitorProfile.default_start_lat,
            VisitorProfile.default_start_lon,
        )
        .filter(VisitorProfile.visitor_code.in_(visitor_codes))
        .all()
    )
    existing_codes = {code for code, _, _ in profile_rows}
    profile_defaults = {
        code: (default_start_lat, default_start_lon)
        for code, default_start_lat, default_start_lon in profile_rows
    }
    unknown_codes = sorted(visitor_codes - existing_codes)
    if unknown_codes:
        unknown_str = ", ".join(unknown_codes)
        errors.append(f"Unknown visitor_code values: {unknown_str}")

    missing_daily_coordinates = df[df["start_lat"].isna() & df["start_lon"].isna()]
    for idx, row in missing_daily_coordinates.iterrows():
        visitor_code = row["visitor_code"]
        if visitor_code not in profile_defaults:
            continue
        default_start_lat, default_start_lon = profile_defaults[visitor_code]
        if default_start_lat is None or default_start_lon is None:
            errors.append(
                _row_error_message(
                    idx,
                    "start_lat/start_lon are empty and visitor has no default start point.",
                )
            )

    if errors:
        raise ValueError("\n".join(sorted(set(errors))))


def upsert_daily_visitor_statuses(df: pd.DataFrame, db: Session) -> int:
    visitor_rows = db.query(VisitorProfile.id, VisitorProfile.visitor_code).all()
    visitor_code_to_id = {code: visitor_id for visitor_id, code in visitor_rows}

    processed_count = 0
    try:
        for _, row in df.iterrows():
            visitor_id = visitor_code_to_id[row["visitor_code"]]
            work_date: date = row["work_date"]
            capacity_value = int(row["capacity_numeric"])

            existing_status = (
                db.query(DailyVisitorStatus)
                .filter(
                    DailyVisitorStatus.visitor_id == visitor_id,
                    DailyVisitorStatus.work_date == work_date,
                )
                .first()
            )

            if existing_status:
                existing_status.start_lat = (
                    None if pd.isna(row["start_lat"]) else float(row["start_lat"])
                )
                existing_status.start_lon = (
                    None if pd.isna(row["start_lon"]) else float(row["start_lon"])
                )
                existing_status.capacity = capacity_value
                existing_status.is_active_today = bool(row["is_active_today"])
            else:
                new_status = DailyVisitorStatus(
                    visitor_id=visitor_id,
                    work_date=work_date,
                    start_lat=None if pd.isna(row["start_lat"]) else float(row["start_lat"]),
                    start_lon=None if pd.isna(row["start_lon"]) else float(row["start_lon"]),
                    capacity=capacity_value,
                    is_active_today=bool(row["is_active_today"]),
                )
                db.add(new_status)

            processed_count += 1

        db.commit()
        return processed_count
    except Exception:
        db.rollback()
        raise


def import_daily_visitor_statuses_from_excel(file_path: str | Path, db: Session) -> int:
    df = read_daily_visitor_status_excel(file_path)
    df = normalize_column_names(df)
    validate_daily_visitor_status_columns(df)
    df = transform_daily_visitor_status_dataframe(df)
    validate_daily_visitor_status_values(df, db)
    return upsert_daily_visitor_statuses(df, db)
