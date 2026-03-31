import os
from tempfile import NamedTemporaryFile

import pandas as pd

from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.db.database import get_db_session


def _run_case(df: pd.DataFrame, expected_message_part: str, title: str) -> None:
    temp_path = None
    db = get_db_session()
    try:
        with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            temp_path = tmp.name
        df.to_excel(temp_path, index=False)

        try:
            import_daily_visitor_statuses_from_excel(temp_path, db)
        except ValueError as exc:
            if expected_message_part not in str(exc):
                raise AssertionError(
                    f"{title}: expected message containing '{expected_message_part}', got '{exc}'"
                ) from exc
            print(f"{title}: OK")
            return

        raise AssertionError(f"{title}: expected ValueError but import succeeded.")
    finally:
        db.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def main():
    base_df = pd.DataFrame(
        [
            {
                "work_date": "2026-03-31",
                "visitor_code": "VIS-001",
                "start_lat": 35.7090,
                "start_lon": 51.4050,
                "capacity": 30,
                "is_active_today": True,
            }
        ]
    )

    missing_column_df = base_df.drop(columns=["capacity"])
    _run_case(missing_column_df, "Missing required columns", "missing required column")

    invalid_date_df = base_df.copy()
    invalid_date_df.loc[0, "work_date"] = "not-a-date"
    _run_case(invalid_date_df, "work_date is invalid", "invalid date format")

    unknown_visitor_df = base_df.copy()
    unknown_visitor_df.loc[0, "visitor_code"] = "VIS-999"
    _run_case(unknown_visitor_df, "Unknown visitor_code values", "unknown visitor_code")

    negative_capacity_df = base_df.copy()
    negative_capacity_df.loc[0, "capacity"] = -1
    _run_case(negative_capacity_df, "capacity cannot be negative", "negative capacity")

    non_integer_capacity_df = base_df.copy()
    non_integer_capacity_df["capacity"] = non_integer_capacity_df["capacity"].astype(float)
    non_integer_capacity_df.loc[0, "capacity"] = 10.5
    _run_case(non_integer_capacity_df, "capacity must be an integer value", "non-integer capacity")

    half_missing_coordinate_df = base_df.copy()
    half_missing_coordinate_df.loc[0, "start_lon"] = None
    _run_case(
        half_missing_coordinate_df,
        "start_lat and start_lon must both be present or both be empty",
        "half-missing coordinate pair",
    )

    duplicate_pair_df = pd.concat([base_df, base_df], ignore_index=True)
    _run_case(
        duplicate_pair_df,
        "duplicate (visitor_code, work_date) found in file",
        "duplicate visitor/date rows",
    )


if __name__ == "__main__":
    main()
