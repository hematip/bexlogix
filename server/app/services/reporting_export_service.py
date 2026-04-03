from datetime import date
from io import BytesIO

import pandas as pd
from sqlalchemy.orm import Session

from server.app.enums.visit_result import VisitResult
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import scheduling_service


def get_daily_kpis(db: Session, work_date: date) -> dict:
    due_stores = len(scheduling_service.get_due_store_ids(db, work_date))

    assigned_stores = (
        db.query(DailyAssignment)
        .filter(DailyAssignment.work_date == work_date)
        .count()
    )
    completed_visits = (
        db.query(Visit)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(DailyAssignment.work_date == work_date)
        .count()
    )

    green_count = (
        db.query(Visit)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(
            DailyAssignment.work_date == work_date,
            Visit.result == VisitResult.GREEN.value,
        )
        .count()
    )
    yellow_count = (
        db.query(Visit)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(
            DailyAssignment.work_date == work_date,
            Visit.result == VisitResult.YELLOW.value,
        )
        .count()
    )
    red_count = (
        db.query(Visit)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(
            DailyAssignment.work_date == work_date,
            Visit.result == VisitResult.RED.value,
        )
        .count()
    )

    telesales_queue_size = (
        db.query(StoreScheduleState)
        .join(Store, Store.id == StoreScheduleState.store_id)
        .filter(
            Store.is_active.is_(True),
            StoreScheduleState.in_telesales_queue.is_(True),
        )
        .count()
    )

    return {
        "work_date": work_date.isoformat(),
        "due_stores": due_stores,
        "assigned_stores": assigned_stores,
        "completed_visits": completed_visits,
        "green": green_count,
        "yellow": yellow_count,
        "red": red_count,
        "telesales_queue_size": telesales_queue_size,
    }


def export_visitor_route_excel(db: Session, work_date: date, visitor_id: int) -> BytesIO:
    rows = (
        db.query(DailyAssignment, Store, VisitorProfile)
        .join(Store, Store.id == DailyAssignment.store_id)
        .join(VisitorProfile, VisitorProfile.id == DailyAssignment.visitor_id)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.visitor_id == visitor_id,
        )
        .order_by(
            DailyAssignment.route_order.is_(None),
            DailyAssignment.route_order,
            Store.store_code,
        )
        .all()
    )

    data = []
    for assignment, store, visitor in rows:
        data.append(
            {
                "work_date": assignment.work_date.isoformat(),
                "visitor_code": visitor.visitor_code,
                "store_code": store.store_code,
                "store_name": store.store_name,
                "region": store.region,
                "address": store.address,
                "lat": store.lat,
                "lon": store.lon,
                "route_order": assignment.route_order,
                "route_distance_km": assignment.route_distance_km,
                "assignment_status": assignment.assignment_status,
            }
        )

    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="route", index=False)
    output.seek(0)
    return output


def export_manager_daily_summary_excel(db: Session, work_date: date) -> BytesIO:
    kpis = get_daily_kpis(db, work_date)
    kpi_df = pd.DataFrame([kpis])

    assignment_detail_columns = [
        "work_date",
        "assignment_id",
        "visitor_code",
        "store_code",
        "store_name",
        "region",
        "address",
        "lat",
        "lon",
        "route_order",
        "route_distance_km",
        "assignment_status",
        "published_at",
        "visit_id",
        "visit_date",
        "visit_result",
        "visit_note",
    ]
    visit_detail_columns = [
        "work_date",
        "visit_id",
        "assignment_id",
        "visit_date",
        "visitor_code",
        "store_code",
        "store_name",
        "result",
        "note",
    ]
    telesales_detail_columns = [
        "work_date",
        "followup_id",
        "followup_date",
        "visitor_code",
        "store_code",
        "store_name",
        "visit_id",
        "visit_result",
        "contact_status",
        "followup_result",
        "queue_status",
        "created_by",
        "note",
    ]

    assignment_rows = (
        db.query(DailyAssignment, VisitorProfile, Store, Visit)
        .join(VisitorProfile, VisitorProfile.id == DailyAssignment.visitor_id)
        .join(Store, Store.id == DailyAssignment.store_id)
        .outerjoin(Visit, Visit.assignment_id == DailyAssignment.id)
        .filter(DailyAssignment.work_date == work_date)
        .order_by(
            VisitorProfile.visitor_code,
            DailyAssignment.route_order.is_(None),
            DailyAssignment.route_order,
            Store.store_code,
        )
        .all()
    )
    assignment_detail_rows = []
    visit_detail_rows = []
    for assignment, visitor, store, visit in assignment_rows:
        assignment_detail_rows.append(
            {
                "work_date": assignment.work_date.isoformat(),
                "assignment_id": assignment.id,
                "visitor_code": visitor.visitor_code,
                "store_code": store.store_code,
                "store_name": store.store_name,
                "region": store.region,
                "address": store.address,
                "lat": store.lat,
                "lon": store.lon,
                "route_order": assignment.route_order,
                "route_distance_km": assignment.route_distance_km,
                "assignment_status": assignment.assignment_status,
                "published_at": (
                    assignment.published_at.isoformat() if assignment.published_at else None
                ),
                "visit_id": visit.id if visit else None,
                "visit_date": visit.visit_date.isoformat() if visit else None,
                "visit_result": visit.result if visit else None,
                "visit_note": visit.note if visit else None,
            }
        )

        if visit:
            visit_detail_rows.append(
                {
                    "work_date": assignment.work_date.isoformat(),
                    "visit_id": visit.id,
                    "assignment_id": assignment.id,
                    "visit_date": visit.visit_date.isoformat(),
                    "visitor_code": visitor.visitor_code,
                    "store_code": store.store_code,
                    "store_name": store.store_name,
                    "result": visit.result,
                    "note": visit.note,
                }
            )

    assignment_detail_df = pd.DataFrame(assignment_detail_rows, columns=assignment_detail_columns)
    visit_detail_df = pd.DataFrame(visit_detail_rows, columns=visit_detail_columns)

    telesales_rows = (
        db.query(TelesalesFollowup, Store, Visit, DailyAssignment, VisitorProfile)
        .join(Store, Store.id == TelesalesFollowup.store_id)
        .join(Visit, Visit.id == TelesalesFollowup.visit_id)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .join(VisitorProfile, VisitorProfile.id == DailyAssignment.visitor_id)
        .filter(DailyAssignment.work_date == work_date)
        .order_by(TelesalesFollowup.followup_date, Store.store_code)
        .all()
    )
    telesales_detail_rows = []
    for followup, store, visit, assignment, visitor in telesales_rows:
        telesales_detail_rows.append(
            {
                "work_date": assignment.work_date.isoformat(),
                "followup_id": followup.id,
                "followup_date": followup.followup_date.isoformat(),
                "visitor_code": visitor.visitor_code,
                "store_code": store.store_code,
                "store_name": store.store_name,
                "visit_id": followup.visit_id,
                "visit_result": visit.result,
                "contact_status": followup.contact_status,
                "followup_result": followup.result,
                "queue_status": "pending" if followup.result is None else "completed",
                "created_by": followup.created_by,
                "note": followup.note,
            }
        )

    telesales_detail_df = pd.DataFrame(telesales_detail_rows, columns=telesales_detail_columns)

    if assignment_detail_df.empty:
        visitor_summary_df = pd.DataFrame(
            columns=[
                "visitor_code",
                "assigned_stores",
                "completed_visits",
                "green",
                "yellow",
                "red",
                "pending_telesales",
                "distance_km",
                "completed_rate_pct",
            ]
        )
    else:
        visitor_rows: list[dict] = []
        for visitor_code, group in assignment_detail_df.groupby("visitor_code", dropna=False):
            assigned_stores = int(len(group))
            completed_visits = int(group["visit_id"].notna().sum())
            green_count = int((group["visit_result"] == VisitResult.GREEN.value).sum())
            yellow_count = int((group["visit_result"] == VisitResult.YELLOW.value).sum())
            red_count = int((group["visit_result"] == VisitResult.RED.value).sum())

            if "route_distance_km" in group.columns:
                numeric_distance = pd.to_numeric(group["route_distance_km"], errors="coerce")
                distance_km = round(float(numeric_distance.max()), 3) if numeric_distance.notna().any() else 0.0
            else:
                distance_km = 0.0

            pending_telesales = 0
            if not telesales_detail_df.empty:
                pending_telesales = int(
                    (
                        (telesales_detail_df["visitor_code"] == visitor_code)
                        & (telesales_detail_df["queue_status"] == "pending")
                    ).sum()
                )

            completed_rate_pct = round(
                (completed_visits / assigned_stores * 100.0) if assigned_stores else 0.0,
                2,
            )

            visitor_rows.append(
                {
                    "visitor_code": visitor_code,
                    "assigned_stores": assigned_stores,
                    "completed_visits": completed_visits,
                    "green": green_count,
                    "yellow": yellow_count,
                    "red": red_count,
                    "pending_telesales": pending_telesales,
                    "distance_km": distance_km,
                    "completed_rate_pct": completed_rate_pct,
                }
            )

        visitor_summary_df = pd.DataFrame(visitor_rows).sort_values("visitor_code")

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        kpi_df.to_excel(writer, sheet_name="kpis", index=False)
        visitor_summary_df.to_excel(writer, sheet_name="visitor_summary", index=False)
        assignment_detail_df.to_excel(writer, sheet_name="assignments_detail", index=False)
        visit_detail_df.to_excel(writer, sheet_name="visits_detail", index=False)
        telesales_detail_df.to_excel(writer, sheet_name="telesales_detail", index=False)
    output.seek(0)
    return output
