# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest

from server.app.models.daily_assignment import DailyAssignment
from server.app.services.reporting_export_service import export_manager_daily_summary_excel
from server.db.database import get_db_session

EXPECTED_SHEETS = [
    "kpis",
    "visitor_summary",
    "assignments_detail",
    "visits_detail",
    "telesales_detail",
]


# Contract: _assert_columns executes one deterministic step in the workflow.
def _assert_columns(df: pd.DataFrame, required_columns: list[str], sheet_name: str) -> None:
    missing_columns = [column for column in required_columns if column not in df.columns]
    assert not missing_columns, (
        f"Sheet '{sheet_name}' is missing required columns: {', '.join(missing_columns)}"
    )


# Contract: test_daily_summary_detailed_export_contract executes one deterministic step in the workflow.
@pytest.mark.integration
def test_daily_summary_detailed_export_contract() -> None:
    db = get_db_session()
    try:
        row = (
            db.query(DailyAssignment.work_date)
            .order_by(DailyAssignment.work_date.desc())
            .first()
        )
        if not row:
            pytest.skip("No assignment data found. Skipping summary export test.")
        work_date = row[0]
        buffer = export_manager_daily_summary_excel(db=db, work_date=work_date)
    finally:
        db.close()

    excel_file = pd.ExcelFile(BytesIO(buffer.getvalue()))
    assert excel_file.sheet_names == EXPECTED_SHEETS

    kpis_df = pd.read_excel(BytesIO(buffer.getvalue()), sheet_name="kpis")
    visitor_summary_df = pd.read_excel(BytesIO(buffer.getvalue()), sheet_name="visitor_summary")
    assignments_df = pd.read_excel(BytesIO(buffer.getvalue()), sheet_name="assignments_detail")
    visits_df = pd.read_excel(BytesIO(buffer.getvalue()), sheet_name="visits_detail")
    telesales_df = pd.read_excel(BytesIO(buffer.getvalue()), sheet_name="telesales_detail")

    _assert_columns(
        kpis_df,
        [
            "work_date",
            "due_stores",
            "assigned_stores",
            "completed_visits",
            "green",
            "yellow",
            "red",
            "telesales_queue_size",
        ],
        "kpis",
    )
    _assert_columns(
        visitor_summary_df,
        [
            "visitor_code",
            "assigned_stores",
            "completed_visits",
            "green",
            "yellow",
            "red",
            "pending_telesales",
            "distance_km",
            "completed_rate_pct",
        ],
        "visitor_summary",
    )
    _assert_columns(
        assignments_df,
        [
            "assignment_id",
            "visitor_code",
            "store_code",
            "route_order",
            "route_distance_km",
            "assignment_status",
            "visit_result",
        ],
        "assignments_detail",
    )
    _assert_columns(
        visits_df,
        [
            "visit_id",
            "assignment_id",
            "visit_date",
            "visitor_code",
            "store_code",
            "result",
        ],
        "visits_detail",
    )
    _assert_columns(
        telesales_df,
        [
            "followup_id",
            "followup_date",
            "visitor_code",
            "store_code",
            "visit_result",
            "queue_status",
        ],
        "telesales_detail",
    )
