# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from datetime import date

import pandas as pd
from sqlalchemy.orm import Session

from server.app.repositories import assignment_repository, visit_repository, visitor_repository


# Contract: get_visitor_options executes one deterministic step in the workflow.
def get_visitor_options(db: Session, work_date: date) -> dict[str, int]:
    rows = visitor_repository.list_visitor_code_rows_for_date(db=db, work_date=work_date)
    return {str(code): int(visitor_id) for visitor_id, code in rows}


# Contract: get_daily_status_row_count executes one deterministic step in the workflow.
def get_daily_status_row_count(db: Session, work_date: date) -> int:
    return visitor_repository.count_daily_status_rows_for_date(db=db, work_date=work_date)


# Contract: load_manager_assignments_df executes one deterministic step in the workflow.
def load_manager_assignments_df(db: Session, work_date: date) -> pd.DataFrame:
    rows = assignment_repository.list_rows_for_assignment_table(db=db, work_date=work_date)
    return pd.DataFrame(
        [
            {
                "assignment_id": row.assignment_id,
                "work_date": row.work_date,
                "visitor_code": row.visitor_code,
                "store_code": row.store_code,
                "store_name": row.store_name,
                "route_order": row.route_order,
                "route_distance_km": row.route_distance_km,
                "assignment_status": row.assignment_status,
                "visit_result": row.visit_result,
            }
            for row in rows
        ]
    )


# Contract: load_route_map_df executes one deterministic step in the workflow.
def load_route_map_df(db: Session, work_date: date, visitor_id: int) -> pd.DataFrame:
    rows = assignment_repository.list_rows_for_route_map(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
    )
    return pd.DataFrame(
        [
            {
                "assignment_id": row.assignment_id,
                "work_date": row.work_date,
                "visitor_code": row.visitor_code,
                "store_code": row.store_code,
                "store_name": row.store_name,
                "lat": row.lat,
                "lon": row.lon,
                "route_order": row.route_order,
                "assignment_status": row.assignment_status,
                "start_lat": (
                    row.start_lat if row.start_lat is not None else row.default_start_lat
                ),
                "start_lon": (
                    row.start_lon if row.start_lon is not None else row.default_start_lon
                ),
            }
            for row in rows
        ]
    )


# Contract: load_supervisor_assignments_df executes one deterministic step in the workflow.
def load_supervisor_assignments_df(db: Session, work_date: date) -> pd.DataFrame:
    df = load_manager_assignments_df(db=db, work_date=work_date)
    if "assignment_id" in df.columns:
        df = df.drop(columns=["assignment_id"])
    return df


# Contract: load_supervisor_visits_df executes one deterministic step in the workflow.
def load_supervisor_visits_df(db: Session, work_date: date) -> pd.DataFrame:
    rows = visit_repository.list_rows_for_visit_table(db=db, work_date=work_date)
    return pd.DataFrame(
        [
            {
                "visit_id": row.visit_id,
                "visit_date": row.visit_date,
                "visitor_code": row.visitor_code,
                "store_code": row.store_code,
                "result": row.result,
                "note": row.note,
            }
            for row in rows
        ]
    )


# Contract: get_visitor_profile_for_user executes one deterministic step in the workflow.
def get_visitor_profile_for_user(db: Session, user_id: int):
    return visitor_repository.get_profile_by_user_id(db=db, user_id=user_id)


# Contract: load_visitor_assignments_df executes one deterministic step in the workflow.
def load_visitor_assignments_df(db: Session, work_date: date, visitor_id: int) -> pd.DataFrame:
    rows = assignment_repository.list_rows_for_visitor_panel(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
    )
    return pd.DataFrame(
        [
            {
                "assignment_id": row.assignment_id,
                "work_date": row.work_date,
                "store_code": row.store_code,
                "store_name": row.store_name,
                "address": row.address,
                "lat": row.lat,
                "lon": row.lon,
                "route_order": row.route_order,
                "route_distance_km": row.route_distance_km,
                "assignment_status": row.assignment_status,
                "start_lat": (
                    row.start_lat if row.start_lat is not None else row.default_start_lat
                ),
                "start_lon": (
                    row.start_lon if row.start_lon is not None else row.default_start_lon
                ),
                "visit_id": row.visit_id,
                "visit_result": row.visit_result,
                "visit_note": row.visit_note,
            }
            for row in rows
        ]
    )
