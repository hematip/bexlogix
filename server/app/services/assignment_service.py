from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.roles import UserRole
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.models.user import User
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import scheduling_service


def _assert_manager_user(db: Session, manager_user_id: int) -> None:
    user = db.query(User).filter(User.id == manager_user_id).first()
    if not user:
        raise ValueError(f"Manager user id {manager_user_id} not found.")
    if user.role != UserRole.MANAGER.value:
        raise ValueError("Only manager users can generate or publish assignments.")


def get_active_visitor_day_contexts(db: Session, work_date: date) -> list[dict]:
    rows = (
        db.query(
            VisitorProfile.id.label("visitor_id"),
            VisitorProfile.visitor_code,
            VisitorProfile.default_start_lat,
            VisitorProfile.default_start_lon,
            VisitorProfile.default_capacity,
            DailyVisitorStatus.start_lat,
            DailyVisitorStatus.start_lon,
            DailyVisitorStatus.capacity,
            DailyVisitorStatus.is_active_today,
            User.is_active.label("user_is_active"),
            VisitorProfile.is_active.label("profile_is_active"),
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

    contexts: list[dict] = []
    for row in rows:
        if not row.user_is_active or not row.profile_is_active:
            continue

        is_active_today = True if row.is_active_today is None else bool(row.is_active_today)
        if not is_active_today:
            continue

        capacity_value = (
            row.capacity
            if row.capacity is not None
            else (row.default_capacity if row.default_capacity is not None else 30)
        )
        capacity_value = int(capacity_value)
        if capacity_value <= 0:
            continue

        start_lat = row.start_lat if row.start_lat is not None else row.default_start_lat
        start_lon = row.start_lon if row.start_lon is not None else row.default_start_lon

        contexts.append(
            {
                "visitor_id": row.visitor_id,
                "visitor_code": row.visitor_code,
                "start_lat": start_lat,
                "start_lon": start_lon,
                "capacity": capacity_value,
            }
        )

    contexts.sort(key=lambda item: item["visitor_code"])
    return contexts


def _get_due_stores_sorted(db: Session, work_date: date) -> list[Store]:
    due_store_ids = scheduling_service.get_due_store_ids(db, work_date)
    if not due_store_ids:
        return []

    stores = db.query(Store).filter(Store.id.in_(due_store_ids)).all()
    states = (
        db.query(StoreScheduleState)
        .filter(StoreScheduleState.store_id.in_(due_store_ids))
        .all()
    )
    states_by_store_id = {state.store_id: state for state in states}

    def sort_key(store: Store):
        state = states_by_store_id.get(store.id)
        overdue_days = state.overdue_days if state else 0
        next_visit_date = state.next_visit_date if state and state.next_visit_date else date.min
        interval_days = scheduling_service.get_store_visit_interval_days(store)
        return (-overdue_days, interval_days, next_visit_date, store.store_code)

    return sorted(stores, key=sort_key)


def _delete_existing_drafts(db: Session, work_date: date) -> int:
    existing_drafts = (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .all()
    )
    count = len(existing_drafts)
    for row in existing_drafts:
        db.delete(row)
    return count


def generate_draft_assignments(
    db: Session,
    work_date: date,
    manager_user_id: int,
    replace_existing_draft: bool = True,
) -> dict:
    _assert_manager_user(db, manager_user_id)

    existing_non_draft_count = (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status != AssignmentStatus.DRAFT.value,
        )
        .count()
    )
    if existing_non_draft_count > 0:
        raise ValueError(
            "Non-draft assignments already exist for this date. "
            "MVP policy blocks draft regeneration after publish/finalize."
        )

    if replace_existing_draft:
        _delete_existing_drafts(db, work_date)
    else:
        existing_draft_count = (
            db.query(DailyAssignment)
            .filter(
                DailyAssignment.work_date == work_date,
                DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
            )
            .count()
        )
        if existing_draft_count > 0:
            raise ValueError("Draft assignments already exist for this date.")

    visitors = get_active_visitor_day_contexts(db, work_date)
    due_stores = _get_due_stores_sorted(db, work_date)

    remaining_capacity_by_visitor = {
        visitor["visitor_id"]: int(visitor["capacity"]) for visitor in visitors
    }
    assigned_count_by_visitor = {visitor["visitor_id"]: 0 for visitor in visitors}

    created_count = 0
    unassigned_store_ids: list[int] = []

    try:
        for store in due_stores:
            candidate_visitors = [
                visitor_id
                for visitor_id, remaining in remaining_capacity_by_visitor.items()
                if remaining > 0
            ]
            if not candidate_visitors:
                unassigned_store_ids.append(store.id)
                continue

            selected_visitor_id = min(
                candidate_visitors,
                key=lambda visitor_id: (
                    assigned_count_by_visitor[visitor_id],
                    visitor_id,
                ),
            )

            assignment = DailyAssignment(
                work_date=work_date,
                visitor_id=selected_visitor_id,
                store_id=store.id,
                route_order=None,
                route_distance_km=None,
                assignment_status=AssignmentStatus.DRAFT.value,
                generated_by=manager_user_id,
            )
            db.add(assignment)

            remaining_capacity_by_visitor[selected_visitor_id] -= 1
            assigned_count_by_visitor[selected_visitor_id] += 1
            created_count += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "work_date": work_date.isoformat(),
        "active_visitors": len(visitors),
        "due_stores": len(due_stores),
        "created_assignments": created_count,
        "unassigned_due_stores": len(unassigned_store_ids),
        "unassigned_store_ids": unassigned_store_ids,
    }


def get_unassigned_due_store_ids(db: Session, work_date: date) -> list[int]:
    due_store_ids = set(scheduling_service.get_due_store_ids(db, work_date))
    if not due_store_ids:
        return []

    assigned_rows = (
        db.query(DailyAssignment.store_id)
        .filter(DailyAssignment.work_date == work_date)
        .all()
    )
    assigned_store_ids = {store_id for (store_id,) in assigned_rows}
    return sorted(due_store_ids - assigned_store_ids)


def publish_assignments(db: Session, work_date: date, manager_user_id: int) -> int:
    _assert_manager_user(db, manager_user_id)

    draft_assignments = (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.DRAFT.value,
        )
        .all()
    )
    if not draft_assignments:
        raise ValueError("No draft assignments found for this date.")

    try:
        publish_time = datetime.now(timezone.utc)
        for assignment in draft_assignments:
            assignment.assignment_status = AssignmentStatus.PUBLISHED.value
            assignment.published_at = publish_time

        db.commit()
        return len(draft_assignments)
    except Exception:
        db.rollback()
        raise
