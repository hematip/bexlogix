from __future__ import annotations

import os
from tempfile import NamedTemporaryFile

import pandas as pd
import pytest

from server.app.services.import_daily_visitor_status_service import (
    import_daily_visitor_statuses_from_excel,
)
from server.app.services.import_users_service import import_users_from_excel
from server.db.database import get_db_session


def _run_case(df: pd.DataFrame, expected_message_part: str) -> None:
    temp_path = None
    db = get_db_session()
    try:
        with NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            temp_path = tmp.name
        df.to_excel(temp_path, index=False)

        with pytest.raises(ValueError) as exc_info:
            import_daily_visitor_statuses_from_excel(temp_path, db)
        assert expected_message_part in str(exc_info.value)
    finally:
        db.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def _base_df() -> pd.DataFrame:
    return pd.DataFrame(
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


@pytest.mark.service
def test_import_daily_visitor_status_validation_cases() -> None:
    db = get_db_session()
    try:
        import_users_from_excel("data/users_seed_sample_10_visitors.xlsx", db)
    finally:
        db.close()

    base_df = _base_df()
    cases: list[tuple[pd.DataFrame, str]] = [
        (base_df.drop(columns=["capacity"]), "Missing required columns"),
        (
            base_df.assign(work_date="not-a-date"),
            "work_date is invalid",
        ),
        (
            base_df.assign(username="visitor999"),
            "Unknown usernames in users table",
        ),
        (
            base_df.assign(username="manager1"),
            "Daily status only accepts users with role='visitor'",
        ),
        (
            base_df.assign(capacity=-1),
            "capacity cannot be negative",
        ),
        (
            base_df.assign(capacity=10.5),
            "capacity must be an integer value",
        ),
        (
            base_df.assign(start_lon=None),
            "start_lat and start_lon must both be present or both be empty",
        ),
        (
            base_df.assign(start_lat=None, start_lon=None),
            "start_lat and start_lon are required for daily routing",
        ),
        (
            pd.concat([base_df, base_df], ignore_index=True),
            "duplicate (username, visitor_code, work_date)",
        ),
        (
            pd.concat(
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
            ),
            "is mapped to multiple visitor_code values in file",
        ),
    ]

    for frame, expected_error in cases:
        _run_case(frame, expected_error)
