# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from server.app.enums.assignment_status import AssignmentStatus
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.store import Store
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile


# Contract: get_assignment_by_id executes one deterministic step in the workflow.
def get_assignment_by_id(db: Session, assignment_id: int) -> DailyAssignment | None:
    return db.query(DailyAssignment).filter(DailyAssignment.id == assignment_id).first()


# Contract: list_assignments_for_visitor_date executes one deterministic step in the workflow.
def list_assignments_for_visitor_date(
    db: Session,
    work_date: date,
    visitor_id: int,
    status: str | None = None,
) -> list[DailyAssignment]:
    query = db.query(DailyAssignment).filter(
        DailyAssignment.work_date == work_date,
        DailyAssignment.visitor_id == visitor_id,
    )
    if status is not None:
        query = query.filter(DailyAssignment.assignment_status == status)
    return query.all()


# Contract: list_draft_assignments_with_store_for_visitor_date executes one deterministic step in the workflow.
def list_draft_assignments_with_store_for_visitor_date(
    db: Session,
    work_date: date,
    visitor_id: int,
) -> list[tuple[DailyAssignment, Store]]:
    return (
        db.query(DailyAssignment, Store)
        .join(Store, Store.id == DailyAssignment.store_id)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.visitor_id == visitor_id,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .all()
    )


# Contract: count_non_draft_assignments_for_date executes one deterministic step in the workflow.
def count_non_draft_assignments_for_date(db: Session, work_date: date) -> int:
    return (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status != AssignmentStatus.DRAFT.value,
        )
        .count()
    )


# Contract: count_draft_assignments_for_date executes one deterministic step in the workflow.
def count_draft_assignments_for_date(db: Session, work_date: date) -> int:
    return (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .count()
    )


# Contract: count_published_assignments_for_visitor_date executes one deterministic step in the workflow.
def count_published_assignments_for_visitor_date(
    db: Session,
    work_date: date,
    visitor_id: int,
) -> int:
    return (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.visitor_id == visitor_id,
            DailyAssignment.assignment_status == AssignmentStatus.PUBLISHED.value,
        )
        .count()
    )


# Contract: delete_draft_assignments_for_date executes one deterministic step in the workflow.
def delete_draft_assignments_for_date(db: Session, work_date: date) -> int:
    rows = (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .all()
    )
    count = len(rows)
    for row in rows:
        db.delete(row)
    return count


# Contract: list_draft_assignments_for_publish executes one deterministic step in the workflow.
def list_draft_assignments_for_publish(db: Session, work_date: date) -> list[DailyAssignment]:
    return (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .all()
    )


def list_assignments_for_publish(
    db: Session,
    work_date: date,
    include_draft_override: bool = False,
) -> list[DailyAssignment]:
    # FIX: [UX-10] Publish prefers supervisor_approved routes unless manager override is enabled.
    allowed_statuses = [AssignmentStatus.SUPERVISOR_APPROVED.value]
    if include_draft_override:
        allowed_statuses.append(AssignmentStatus.DRAFT.value)
    return (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status.in_(allowed_statuses),
        )
        .all()
    )


# Contract: list_visitor_ids_with_draft_assignments executes one deterministic step in the workflow.
def list_visitor_ids_with_draft_assignments(db: Session, work_date: date) -> list[int]:
    rows = (
        db.query(DailyAssignment.visitor_id)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .distinct()
        .all()
    )
    return [visitor_id for (visitor_id,) in rows]


# Contract: list_assignment_ids_and_store_ids_for_date executes one deterministic step in the workflow.
def list_assignment_ids_and_store_ids_for_date(
    db: Session, work_date: date
) -> list[tuple[int, int]]:
    return (
        db.query(DailyAssignment.id, DailyAssignment.store_id)
        .filter(DailyAssignment.work_date == work_date)
        .all()
    )


# Contract: list_assigned_store_ids_for_date executes one deterministic step in the workflow.
def list_assigned_store_ids_for_date(db: Session, work_date: date) -> list[int]:
    rows = (
        db.query(DailyAssignment.store_id)
        .filter(DailyAssignment.work_date == work_date)
        .all()
    )
    return [int(store_id) for (store_id,) in rows]


# Contract: delete_assignments_for_date executes one deterministic step in the workflow.
def delete_assignments_for_date(db: Session, work_date: date) -> int:
    return (
        db.query(DailyAssignment)
        .filter(DailyAssignment.work_date == work_date)
        .delete(synchronize_session=False)
    )


# Contract: count_assignments_for_date executes one deterministic step in the workflow.
def count_assignments_for_date(db: Session, work_date: date) -> int:
    return db.query(DailyAssignment).filter(DailyAssignment.work_date == work_date).count()


def count_assignments_grouped_by_status(db: Session, work_date: date) -> dict[str, int]:
    # FIX: [UX-05] Provide per-status counts for lock reason visibility.
    rows = (
        db.query(DailyAssignment.assignment_status, DailyAssignment.id)
        .filter(DailyAssignment.work_date == work_date)
        .all()
    )
    counts: dict[str, int] = {}
    for status, _assignment_id in rows:
        normalized = str(status or "").strip().lower()
        counts[normalized] = counts.get(normalized, 0) + 1
    return counts


# Contract: count_visits_linked_to_assignment_date executes one deterministic step in the workflow.
def count_visits_linked_to_assignment_date(db: Session, work_date: date) -> int:
    return (
        db.query(Visit)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(DailyAssignment.work_date == work_date)
        .count()
    )


# Contract: count_followups_linked_to_assignment_date executes one deterministic step in the workflow.
def count_followups_linked_to_assignment_date(db: Session, work_date: date) -> int:
    return (
        db.query(TelesalesFollowup)
        .join(Visit, Visit.id == TelesalesFollowup.visit_id)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(DailyAssignment.work_date == work_date)
        .count()
    )


# Contract: list_rows_for_assignment_table executes one deterministic step in the workflow.
def list_rows_for_assignment_table(db: Session, work_date: date) -> list[tuple]:
    return (
        db.query(
            DailyAssignment.id.label("assignment_id"),
            DailyAssignment.work_date,
            VisitorProfile.visitor_code,
            Store.store_code,
            Store.store_name,
            DailyAssignment.route_order,
            DailyAssignment.route_distance_km,
            DailyAssignment.assignment_status,
            Visit.result.label("visit_result"),
        )
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


# Contract: list_rows_for_route_map executes one deterministic step in the workflow.
def list_rows_for_route_map(db: Session, work_date: date, visitor_id: int) -> list[tuple]:
    return (
        db.query(
            DailyAssignment.id.label("assignment_id"),
            DailyAssignment.work_date,
            VisitorProfile.visitor_code,
            Store.store_code,
            Store.store_name,
            Store.lat,
            Store.lon,
            DailyAssignment.route_order,
            DailyAssignment.assignment_status,
            DailyVisitorStatus.start_lat,
            DailyVisitorStatus.start_lon,
            VisitorProfile.default_start_lat,
            VisitorProfile.default_start_lon,
        )
        .join(VisitorProfile, VisitorProfile.id == DailyAssignment.visitor_id)
        .join(Store, Store.id == DailyAssignment.store_id)
        .outerjoin(
            DailyVisitorStatus,
            (DailyVisitorStatus.visitor_id == DailyAssignment.visitor_id)
            & (DailyVisitorStatus.work_date == DailyAssignment.work_date),
        )
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


# Contract: list_rows_for_visitor_panel executes one deterministic step in the workflow.
def list_rows_for_visitor_panel(db: Session, work_date: date, visitor_id: int) -> list[tuple]:
    return (
        db.query(
            DailyAssignment.id.label("assignment_id"),
            DailyAssignment.work_date,
            Store.store_code,
            Store.store_name,
            Store.address,
            Store.lat,
            Store.lon,
            DailyAssignment.route_order,
            DailyAssignment.route_distance_km,
            DailyAssignment.assignment_status,
            DailyVisitorStatus.start_lat,
            DailyVisitorStatus.start_lon,
            VisitorProfile.default_start_lat,
            VisitorProfile.default_start_lon,
            Visit.id.label("visit_id"),
            Visit.result.label("visit_result"),
            Visit.note.label("visit_note"),
        )
        .join(VisitorProfile, VisitorProfile.id == DailyAssignment.visitor_id)
        .join(Store, Store.id == DailyAssignment.store_id)
        .outerjoin(
            DailyVisitorStatus,
            (DailyVisitorStatus.visitor_id == DailyAssignment.visitor_id)
            & (DailyVisitorStatus.work_date == DailyAssignment.work_date),
        )
        .outerjoin(Visit, Visit.assignment_id == DailyAssignment.id)
        .filter(
            DailyAssignment.visitor_id == visitor_id,
            DailyAssignment.work_date == work_date,
        )
        .order_by(
            DailyAssignment.route_order.is_(None),
            DailyAssignment.route_order,
            Store.store_code,
        )
        .all()
    )
