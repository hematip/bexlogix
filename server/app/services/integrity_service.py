# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.roles import UserRole
from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.user import User
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import scheduling_service
from server.app.services.constants import DEFAULT_DAILY_CAPACITY


# Contract: _issue executes one deterministic step in the workflow.
def _issue(check: str, message: str, rows: list[dict]) -> dict:
    return {
        "check": check,
        "message": message,
        "count": len(rows),
        "rows": rows,
    }


# Contract: _empty_result executes one deterministic step in the workflow.
def _empty_result() -> dict:
    return {"blockers": [], "warnings": []}


# Contract: repair_missing_schedule_states executes one deterministic step in the workflow.
def repair_missing_schedule_states(db: Session, baseline_date: date) -> int:
    """
    Safe repair utility:
    ensure all active stores have a schedule state row.
    """
    return scheduling_service.ensure_store_schedule_state_rows(db, baseline_date)


# Contract: check_duplicate_operational_rows executes one deterministic step in the workflow.
def check_duplicate_operational_rows(db: Session) -> dict:
    result = _empty_result()

    duplicate_daily_status = (
        db.query(
            DailyVisitorStatus.visitor_id,
            DailyVisitorStatus.work_date,
            func.count(DailyVisitorStatus.id).label("row_count"),
        )
        .group_by(DailyVisitorStatus.visitor_id, DailyVisitorStatus.work_date)
        .having(func.count(DailyVisitorStatus.id) > 1)
        .all()
    )
    if duplicate_daily_status:
        rows = [
            {
                "visitor_id": visitor_id,
                "work_date": work_date.isoformat(),
                "row_count": row_count,
            }
            for visitor_id, work_date, row_count in duplicate_daily_status
        ]
        result["blockers"].append(
            _issue(
                "duplicate_daily_visitor_statuses",
                "Duplicate (visitor_id, work_date) rows found in daily_visitor_statuses.",
                rows,
            )
        )

    duplicate_assignments = (
        db.query(
            DailyAssignment.work_date,
            DailyAssignment.store_id,
            func.count(DailyAssignment.id).label("row_count"),
        )
        .group_by(DailyAssignment.work_date, DailyAssignment.store_id)
        .having(func.count(DailyAssignment.id) > 1)
        .all()
    )
    if duplicate_assignments:
        rows = [
            {
                "work_date": work_date.isoformat(),
                "store_id": store_id,
                "row_count": row_count,
            }
            for work_date, store_id, row_count in duplicate_assignments
        ]
        result["blockers"].append(
            _issue(
                "duplicate_daily_assignments",
                "Duplicate (work_date, store_id) rows found in daily_assignments.",
                rows,
            )
        )

    duplicate_visits = (
        db.query(
            Visit.assignment_id,
            func.count(Visit.id).label("row_count"),
        )
        .group_by(Visit.assignment_id)
        .having(func.count(Visit.id) > 1)
        .all()
    )
    if duplicate_visits:
        rows = [
            {"assignment_id": assignment_id, "row_count": row_count}
            for assignment_id, row_count in duplicate_visits
        ]
        result["blockers"].append(
            _issue(
                "duplicate_visits_per_assignment",
                "Multiple visit rows detected for one assignment.",
                rows,
            )
        )

    duplicate_schedule_states = (
        db.query(
            StoreScheduleState.store_id,
            func.count(StoreScheduleState.id).label("row_count"),
        )
        .group_by(StoreScheduleState.store_id)
        .having(func.count(StoreScheduleState.id) > 1)
        .all()
    )
    if duplicate_schedule_states:
        rows = [
            {"store_id": store_id, "row_count": row_count}
            for store_id, row_count in duplicate_schedule_states
        ]
        result["blockers"].append(
            _issue(
                "duplicate_store_schedule_states",
                "Multiple schedule state rows detected for one store.",
                rows,
            )
        )

    duplicate_open_followups = (
        db.query(
            TelesalesFollowup.visit_id,
            func.count(TelesalesFollowup.id).label("row_count"),
        )
        .filter(TelesalesFollowup.result.is_(None))
        .group_by(TelesalesFollowup.visit_id)
        .having(func.count(TelesalesFollowup.id) > 1)
        .all()
    )
    if duplicate_open_followups:
        rows = [
            {"visit_id": visit_id, "row_count": row_count}
            for visit_id, row_count in duplicate_open_followups
        ]
        result["blockers"].append(
            _issue(
                "duplicate_open_followups_per_visit",
                "Multiple open follow-ups found for a single visit.",
                rows,
            )
        )

    return result


# Contract: check_followup_visit_store_consistency executes one deterministic step in the workflow.
def check_followup_visit_store_consistency(db: Session) -> dict:
    result = _empty_result()
    mismatches = (
        db.query(
            TelesalesFollowup.id,
            TelesalesFollowup.store_id,
            TelesalesFollowup.visit_id,
            Visit.store_id.label("visit_store_id"),
        )
        .join(Visit, Visit.id == TelesalesFollowup.visit_id)
        .filter(TelesalesFollowup.store_id != Visit.store_id)
        .all()
    )
    if mismatches:
        rows = [
            {
                "followup_id": followup_id,
                "followup_store_id": followup_store_id,
                "visit_id": visit_id,
                "visit_store_id": visit_store_id,
            }
            for followup_id, followup_store_id, visit_id, visit_store_id in mismatches
        ]
        result["blockers"].append(
            _issue(
                "followup_visit_store_mismatch",
                "TelesalesFollowup.store_id does not match Visit.store_id.",
                rows,
            )
        )
    return result


# Contract: check_postpone_chain_consistency executes one deterministic step in the workflow.
def check_postpone_chain_consistency(db: Session) -> dict:
    result = _empty_result()
    postponed_rows = (
        db.query(TelesalesFollowup.id, TelesalesFollowup.visit_id, TelesalesFollowup.followup_date)
        .filter(TelesalesFollowup.result == TelesalesOutcome.POSTPONE.value)
        .all()
    )

    missing_chain_rows: list[dict] = []
    for followup_id, visit_id, followup_date in postponed_rows:
        next_open_followup = (
            db.query(TelesalesFollowup.id)
            .filter(
                TelesalesFollowup.visit_id == visit_id,
                TelesalesFollowup.result.is_(None),
                TelesalesFollowup.followup_date > followup_date,
            )
            .first()
        )
        if next_open_followup is None:
            missing_chain_rows.append(
                {
                    "followup_id": followup_id,
                    "visit_id": visit_id,
                    "followup_date": followup_date.isoformat(),
                }
            )

    if missing_chain_rows:
        result["blockers"].append(
            _issue(
                "postpone_without_next_open_followup",
                "A postpone outcome exists without a newer open follow-up for the same visit.",
                missing_chain_rows,
            )
        )
    return result


# Contract: check_queue_flag_consistency executes one deterministic step in the workflow.
def check_queue_flag_consistency(db: Session) -> dict:
    result = _empty_result()

    pending_by_store = {
        store_id: pending_count
        for store_id, pending_count in (
            db.query(
                TelesalesFollowup.store_id,
                func.count(TelesalesFollowup.id),
            )
            .filter(TelesalesFollowup.result.is_(None))
            .group_by(TelesalesFollowup.store_id)
            .all()
        )
    }
    state_by_store = {
        store_id: in_telesales_queue
        for store_id, in_telesales_queue in (
            db.query(StoreScheduleState.store_id, StoreScheduleState.in_telesales_queue).all()
        )
    }

    missing_schedule_state_rows = [
        {"store_id": store_id, "pending_followups": pending_count}
        for store_id, pending_count in pending_by_store.items()
        if store_id not in state_by_store
    ]
    if missing_schedule_state_rows:
        result["blockers"].append(
            _issue(
                "missing_schedule_state_for_pending_followup",
                "Pending telesales follow-up exists for store without schedule state row.",
                missing_schedule_state_rows,
            )
        )

    queue_mismatch_rows = []
    for store_id, queue_flag in state_by_store.items():
        expected_flag = bool(pending_by_store.get(store_id, 0) > 0)
        if bool(queue_flag) != expected_flag:
            queue_mismatch_rows.append(
                {
                    "store_id": store_id,
                    "queue_flag": bool(queue_flag),
                    "expected_queue_flag": expected_flag,
                    "pending_followups": pending_by_store.get(store_id, 0),
                }
            )

    if queue_mismatch_rows:
        result["blockers"].append(
            _issue(
                "schedule_queue_flag_mismatch",
                "Store schedule queue flag is inconsistent with open telesales follow-ups.",
                queue_mismatch_rows,
            )
        )

    return result


# Contract: check_published_assignments_vs_visits executes one deterministic step in the workflow.
def check_published_assignments_vs_visits(db: Session, work_date: date) -> dict:
    result = _empty_result()

    published_visit_counts = (
        db.query(
            DailyAssignment.id,
            func.count(Visit.id).label("visit_count"),
        )
        .outerjoin(Visit, Visit.assignment_id == DailyAssignment.id)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.PUBLISHED.value,
        )
        .group_by(DailyAssignment.id)
        .all()
    )

    duplicate_visit_rows = [
        {"assignment_id": assignment_id, "visit_count": visit_count}
        for assignment_id, visit_count in published_visit_counts
        if int(visit_count) > 1
    ]
    if duplicate_visit_rows:
        result["blockers"].append(
            _issue(
                "published_assignment_with_multiple_visits",
                "A published assignment has multiple visits.",
                duplicate_visit_rows,
            )
        )

    missing_visit_rows = [
        {"assignment_id": assignment_id}
        for assignment_id, visit_count in published_visit_counts
        if int(visit_count) == 0
    ]
    if missing_visit_rows:
        result["warnings"].append(
            _issue(
                "published_assignment_without_visit",
                "Published assignment has no visit yet (may be valid during the day).",
                missing_visit_rows,
            )
        )

    return result


# Contract: check_daily_status_routing_readiness executes one deterministic step in the workflow.
def check_daily_status_routing_readiness(db: Session, work_date: date) -> dict:
    result = _empty_result()

    rows = (
        db.query(
            VisitorProfile.id,
            VisitorProfile.visitor_code,
            VisitorProfile.default_start_lat,
            VisitorProfile.default_start_lon,
            VisitorProfile.default_capacity,
            VisitorProfile.is_active.label("profile_is_active"),
            User.is_active.label("user_is_active"),
            DailyVisitorStatus.start_lat,
            DailyVisitorStatus.start_lon,
            DailyVisitorStatus.capacity,
            DailyVisitorStatus.is_active_today,
        )
        .join(User, User.id == VisitorProfile.user_id)
        .outerjoin(
            DailyVisitorStatus,
            (DailyVisitorStatus.visitor_id == VisitorProfile.id)
            & (DailyVisitorStatus.work_date == work_date),
        )
        .filter(User.role == UserRole.VISITOR.value)
        .all()
    )

    active_routable_count = 0
    readiness_blockers: list[dict] = []
    readiness_warnings: list[dict] = []

    for row in rows:
        if not row.profile_is_active or not row.user_is_active:
            continue

        is_active_today = True if row.is_active_today is None else bool(row.is_active_today)
        if not is_active_today:
            continue

        daily_capacity = row.capacity if row.capacity is not None else row.default_capacity
        if daily_capacity is None:
            daily_capacity = DEFAULT_DAILY_CAPACITY
        daily_capacity = int(daily_capacity)

        start_lat = row.start_lat if row.start_lat is not None else row.default_start_lat
        start_lon = row.start_lon if row.start_lon is not None else row.default_start_lon

        if (start_lat is None) ^ (start_lon is None):
            readiness_blockers.append(
                {
                    "visitor_id": row.id,
                    "visitor_code": row.visitor_code,
                    "issue": "partial_start_coordinate_pair",
                }
            )
            continue

        if start_lat is None and start_lon is None:
            readiness_blockers.append(
                {
                    "visitor_id": row.id,
                    "visitor_code": row.visitor_code,
                    "issue": "missing_start_coordinate_pair",
                }
            )
            continue

        if daily_capacity <= 0:
            readiness_warnings.append(
                {
                    "visitor_id": row.id,
                    "visitor_code": row.visitor_code,
                    "issue": "non_positive_capacity",
                    "capacity": daily_capacity,
                }
            )
            continue

        active_routable_count += 1

    if active_routable_count == 0:
        result["blockers"].append(
            _issue(
                "no_routable_active_visitors",
                "No active visitor with valid start point and positive capacity for routing.",
                [{"work_date": work_date.isoformat()}],
            )
        )

    if readiness_blockers:
        result["blockers"].append(
            _issue(
                "daily_status_routing_readiness_blockers",
                "Visitor rows are not routing-ready for the target work date.",
                readiness_blockers,
            )
        )

    if readiness_warnings:
        result["warnings"].append(
            _issue(
                "daily_status_routing_readiness_warnings",
                "Active visitors with non-positive capacity are skipped in assignment.",
                readiness_warnings,
            )
        )

    return result


# Contract: run_integrity_report executes one deterministic step in the workflow.
def run_integrity_report(db: Session, work_date: date, strict: bool = False) -> dict:
    report = {
        "work_date": work_date.isoformat(),
        "strict": strict,
        "blockers": [],
        "warnings": [],
    }

    checks = [
        check_duplicate_operational_rows(db),
        check_followup_visit_store_consistency(db),
        check_postpone_chain_consistency(db),
        check_queue_flag_consistency(db),
        check_published_assignments_vs_visits(db, work_date),
        check_daily_status_routing_readiness(db, work_date),
    ]

    for check_result in checks:
        report["blockers"].extend(check_result["blockers"])
        report["warnings"].extend(check_result["warnings"])

    report["summary"] = {
        "blocker_checks": len(report["blockers"]),
        "warning_checks": len(report["warnings"]),
        "total_blocker_rows": sum(item["count"] for item in report["blockers"]),
        "total_warning_rows": sum(item["count"] for item in report["warnings"]),
        "ok": len(report["blockers"]) == 0,
    }

    return report
