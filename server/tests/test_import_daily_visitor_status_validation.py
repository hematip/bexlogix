import os
from tempfile import NamedTemporaryFile

import pandas as pd

from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.app.services.import_users_service import import_users_from_excel
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


def main() -> None:
    db = get_db_session()
    try:
        import_users_from_excel("data/users_seed_sample_10_visitors.xlsx", db)
    finally:
        db.close()

    base_df = pd.DataFrame(
        [
            {
                "work_date": "2026-04-01",
                "username": "visitor1",
                "visitor_code": "VIS-001",
                "full_name": "ویزیتور 01",
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

    unknown_username_df = base_df.copy()
    unknown_username_df.loc[0, "username"] = "visitor999"
    _run_case(unknown_username_df, "Unknown usernames in users table", "unknown username")

    invalid_role_df = base_df.copy()
    invalid_role_df.loc[0, "username"] = "manager1"
    _run_case(invalid_role_df, "Daily status only accepts users with role='visitor'", "invalid role")

    negative_capacity_df = base_df.copy()
    negative_capacity_df.loc[0, "capacity"] = -1
    _run_case(negative_capacity_df, "capacity cannot be negative", "negative capacity")

    non_integer_capacity_df = base_df.copy()
    non_integer_capacity_df.loc[0, "capacity"] = 10.5
    _run_case(non_integer_capacity_df, "capacity must be an integer value", "non-integer capacity")

    half_missing_coordinate_df = base_df.copy()
    half_missing_coordinate_df.loc[0, "start_lon"] = None
    _run_case(
        half_missing_coordinate_df,
        "start_lat and start_lon must both be present or both be empty",
        "half-missing coordinate pair",
    )

    full_missing_coordinate_df = base_df.copy()
    full_missing_coordinate_df.loc[0, "start_lat"] = None
    full_missing_coordinate_df.loc[0, "start_lon"] = None
    _run_case(
        full_missing_coordinate_df,
        "start_lat and start_lon are required for daily routing",
        "missing coordinate pair",
    )

    duplicate_pair_df = pd.concat([base_df, base_df], ignore_index=True)
    _run_case(
        duplicate_pair_df,
        "duplicate (username, visitor_code, work_date)",
        "duplicate username/visitor/date rows",
    )

    username_multi_codes_df = pd.concat(
        [
            base_df,
            pd.DataFrame(
                [
                    {
                        "work_date": "2026-04-01",
                        "username": "visitor1",
                        "visitor_code": "VIS-999",
                        "full_name": "ویزیتور تست",
                        "start_lat": 35.71,
                        "start_lon": 51.41,
                        "capacity": 20,
                        "is_active_today": True,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    _run_case(
        username_multi_codes_df,
        "is mapped to multiple visitor_code values in file",
        "username mapped to multiple visitor codes",
    )


if __name__ == "__main__":
    main()
