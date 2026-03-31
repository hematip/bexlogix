from datetime import date
from io import BytesIO

import pandas as pd
from sqlalchemy import func
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

    assignment_rows = (
        db.query(DailyAssignment, VisitorProfile, Store)
        .join(VisitorProfile, VisitorProfile.id == DailyAssignment.visitor_id)
        .join(Store, Store.id == DailyAssignment.store_id)
        .filter(DailyAssignment.work_date == work_date)
        .order_by(VisitorProfile.visitor_code, DailyAssignment.route_order, Store.store_code)
        .all()
    )
    assignment_data = []
    for assignment, visitor, store in assignment_rows:
        assignment_data.append(
            {
                "work_date": assignment.work_date.isoformat(),
                "visitor_code": visitor.visitor_code,
                "store_code": store.store_code,
                "store_name": store.store_name,
                "route_order": assignment.route_order,
                "route_distance_km": assignment.route_distance_km,
                "assignment_status": assignment.assignment_status,
            }
        )
    assignment_df = pd.DataFrame(assignment_data)

    visit_rows = (
        db.query(Visit.result, func.count(Visit.id))
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(DailyAssignment.work_date == work_date)
        .group_by(Visit.result)
        .all()
    )
    visit_summary_df = pd.DataFrame(
        [{"result": result, "count": count} for result, count in visit_rows]
    )

    queue_rows = (
        db.query(TelesalesFollowup, Store)
        .join(Store, Store.id == TelesalesFollowup.store_id)
        .filter(TelesalesFollowup.result.is_(None))
        .order_by(TelesalesFollowup.followup_date, Store.store_code)
        .all()
    )
    queue_data = []
    for followup, store in queue_rows:
        queue_data.append(
            {
                "followup_date": followup.followup_date.isoformat(),
                "store_code": store.store_code,
                "store_name": store.store_name,
                "visit_id": followup.visit_id,
                "note": followup.note,
            }
        )
    queue_df = pd.DataFrame(queue_data)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        kpi_df.to_excel(writer, sheet_name="kpis", index=False)
        assignment_df.to_excel(writer, sheet_name="assignments", index=False)
        visit_summary_df.to_excel(writer, sheet_name="visit_summary", index=False)
        queue_df.to_excel(writer, sheet_name="telesales_queue", index=False)
    output.seek(0)
    return output
