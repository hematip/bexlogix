from __future__ import annotations

from datetime import date, datetime, timezone
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.roles import UserRole
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.user import User
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import routing_service, scheduling_service

QUALITY_GATE_THRESHOLD_PCT = 20.0


def _assert_manager_user(db: Session, manager_user_id: int) -> None:
    user = db.query(User).filter(User.id == manager_user_id).first()
    if not user:
        raise ValueError(f"Manager user id {manager_user_id} not found.")
    if user.role != UserRole.MANAGER.value:
        raise ValueError("Only manager users can generate or publish assignments.")


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    c = 2 * asin(sqrt(a))
    return radius_km * c


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


def _select_closest_store_for_visitor(
    visitor_state: dict,
    unassigned_stores: list[Store],
    store_priority: dict[int, int],
) -> tuple[Store, float] | None:
    current_lat = visitor_state.get("current_lat")
    current_lon = visitor_state.get("current_lon")
    if current_lat is None or current_lon is None:
        return None

    nearest_store = min(
        unassigned_stores,
        key=lambda store: (
            _haversine_km(current_lat, current_lon, float(store.lat), float(store.lon))
            + (store_priority.get(store.id, 0) * 0.000001)
        ),
    )
    distance = _haversine_km(
        current_lat,
        current_lon,
        float(nearest_store.lat),
        float(nearest_store.lon),
    )
    return nearest_store, distance


def _geo_capacity_allocate_stores(visitors: list[dict], due_stores: list[Store]) -> dict[int, list[Store]]:
    allocations: dict[int, list[Store]] = {visitor["visitor_id"]: [] for visitor in visitors}
    if not visitors or not due_stores:
        return allocations

    visitor_state = {
        visitor["visitor_id"]: {
            "remaining_capacity": int(visitor["capacity"]),
            "assigned_count": 0,
            "current_lat": (
                float(visitor["start_lat"]) if visitor["start_lat"] is not None else None
            ),
            "current_lon": (
                float(visitor["start_lon"]) if visitor["start_lon"] is not None else None
            ),
        }
        for visitor in visitors
    }

    store_priority = {store.id: index for index, store in enumerate(due_stores)}
    unassigned_stores = due_stores.copy()

    while unassigned_stores:
        active_visitor_ids = [
            visitor["visitor_id"]
            for visitor in visitors
            if visitor_state[visitor["visitor_id"]]["remaining_capacity"] > 0
        ]
        if not active_visitor_ids:
            break

        candidate_pairs: list[tuple[float, int, Store]] = []
        for visitor in visitors:
            visitor_id = visitor["visitor_id"]
            state = visitor_state[visitor_id]
            if state["remaining_capacity"] <= 0:
                continue
            nearest = _select_closest_store_for_visitor(state, unassigned_stores, store_priority)
            if nearest is None:
                continue
            nearest_store, distance = nearest
            candidate_pairs.append((distance, visitor_id, nearest_store))

        if candidate_pairs:
            candidate_pairs.sort(key=lambda item: (item[0], item[1], item[2].store_code))
            _, selected_visitor_id, selected_store = candidate_pairs[0]
        else:
            # Fallback when start points are missing: assign by smallest load.
            selected_visitor_id = min(
                active_visitor_ids,
                key=lambda visitor_id: (
                    visitor_state[visitor_id]["assigned_count"],
                    visitor_id,
                ),
            )
            selected_store = unassigned_stores[0]

        allocations[selected_visitor_id].append(selected_store)
        visitor_state[selected_visitor_id]["remaining_capacity"] -= 1
        visitor_state[selected_visitor_id]["assigned_count"] += 1
        visitor_state[selected_visitor_id]["current_lat"] = float(selected_store.lat)
        visitor_state[selected_visitor_id]["current_lon"] = float(selected_store.lon)
        unassigned_stores.remove(selected_store)

    return allocations


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
    allocations = _geo_capacity_allocate_stores(visitors=visitors, due_stores=due_stores)

    created_count = 0
    assigned_store_ids: set[int] = set()

    try:
        for visitor in visitors:
            visitor_id = int(visitor["visitor_id"])
            for store in allocations.get(visitor_id, []):
                db.add(
                    DailyAssignment(
                        work_date=work_date,
                        visitor_id=visitor_id,
                        store_id=store.id,
                        route_order=None,
                        route_distance_km=None,
                        assignment_status=AssignmentStatus.DRAFT.value,
                        generated_by=manager_user_id,
                    )
                )
                assigned_store_ids.add(store.id)
                created_count += 1

        db.commit()
    except Exception:
        db.rollback()
        raise

    unassigned_store_ids = [store.id for store in due_stores if store.id not in assigned_store_ids]
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


def get_work_date_operational_snapshot(db: Session, work_date: date) -> dict:
    assignment_count = (
        db.query(DailyAssignment)
        .filter(DailyAssignment.work_date == work_date)
        .count()
    )
    non_draft_count = (
        db.query(DailyAssignment)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status != AssignmentStatus.DRAFT.value,
        )
        .count()
    )
    visit_count = (
        db.query(Visit)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(DailyAssignment.work_date == work_date)
        .count()
    )
    followup_count = (
        db.query(TelesalesFollowup)
        .join(Visit, Visit.id == TelesalesFollowup.visit_id)
        .join(DailyAssignment, DailyAssignment.id == Visit.assignment_id)
        .filter(DailyAssignment.work_date == work_date)
        .count()
    )

    return {
        "work_date": work_date.isoformat(),
        "assignment_count": int(assignment_count),
        "non_draft_count": int(non_draft_count),
        "visit_count": int(visit_count),
        "followup_count": int(followup_count),
        "is_locked": bool(non_draft_count > 0 or visit_count > 0 or followup_count > 0),
    }


def _rebuild_store_schedule_state_from_history(
    db: Session,
    store_id: int,
    baseline_date: date,
) -> None:
    state = (
        db.query(StoreScheduleState)
        .filter(StoreScheduleState.store_id == store_id)
        .first()
    )
    if not state:
        state = StoreScheduleState(
            store_id=store_id,
            next_visit_date=baseline_date,
            overdue_days=0,
            in_telesales_queue=False,
        )
        db.add(state)
        db.flush()

    state.last_visit_date = None
    state.last_visit_result = None
    state.next_visit_date = baseline_date
    state.overdue_days = 0
    state.in_telesales_queue = False

    events: list[tuple[date, int, str, str]] = []

    visit_rows = (
        db.query(Visit.visit_date, Visit.result)
        .filter(Visit.store_id == store_id)
        .order_by(Visit.visit_date, Visit.id)
        .all()
    )
    for visit_date, result in visit_rows:
        events.append((visit_date, 0, "visit", result))

    followup_rows = (
        db.query(TelesalesFollowup.followup_date, TelesalesFollowup.result)
        .filter(
            TelesalesFollowup.store_id == store_id,
            TelesalesFollowup.result.is_not(None),
        )
        .order_by(TelesalesFollowup.followup_date, TelesalesFollowup.id)
        .all()
    )
    for followup_date, result in followup_rows:
        events.append((followup_date, 1, "followup", result))

    events.sort(key=lambda item: (item[0], item[1]))

    for event_date, _, event_type, value in events:
        if event_type == "visit":
            scheduling_service.apply_visit_result_to_schedule(
                db=db,
                store_id=store_id,
                visit_date=event_date,
                visit_result=value,
                commit=False,
            )
        else:
            scheduling_service.apply_telesales_outcome_to_schedule(
                db=db,
                store_id=store_id,
                followup_date=event_date,
                outcome=value,
                commit=False,
            )


def flush_work_date_operational_data(db: Session, work_date: date, manager_user_id: int) -> dict:
    _assert_manager_user(db, manager_user_id)

    assignment_rows = (
        db.query(DailyAssignment.id, DailyAssignment.store_id)
        .filter(DailyAssignment.work_date == work_date)
        .all()
    )
    assignment_ids = [int(assignment_id) for assignment_id, _ in assignment_rows]
    affected_store_ids = {int(store_id) for _, store_id in assignment_rows}

    visit_ids: list[int] = []
    if assignment_ids:
        visit_ids = [
            int(visit_id)
            for (visit_id,) in (
                db.query(Visit.id)
                .filter(Visit.assignment_id.in_(assignment_ids))
                .all()
            )
        ]

    followup_deleted = 0
    if visit_ids:
        followup_deleted = (
            db.query(TelesalesFollowup)
            .filter(TelesalesFollowup.visit_id.in_(visit_ids))
            .delete(synchronize_session=False)
        )

    visits_deleted = 0
    if assignment_ids:
        visits_deleted = (
            db.query(Visit)
            .filter(Visit.assignment_id.in_(assignment_ids))
            .delete(synchronize_session=False)
        )

    assignments_deleted = (
        db.query(DailyAssignment)
        .filter(DailyAssignment.work_date == work_date)
        .delete(synchronize_session=False)
    )

    try:
        db.flush()
        for store_id in sorted(affected_store_ids):
            _rebuild_store_schedule_state_from_history(
                db=db,
                store_id=store_id,
                baseline_date=work_date,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {
        "work_date": work_date.isoformat(),
        "assignments_deleted": int(assignments_deleted),
        "visits_deleted": int(visits_deleted),
        "followups_deleted": int(followup_deleted),
        "affected_stores": len(affected_store_ids),
    }


def _calculate_path_length_for_rows(
    start_lat: float | None,
    start_lon: float | None,
    ordered_rows: list[dict],
) -> float:
    if not ordered_rows or start_lat is None or start_lon is None:
        return 0.0

    total = 0.0
    current_lat = float(start_lat)
    current_lon = float(start_lon)
    for row in ordered_rows:
        lat = float(row["lat"])
        lon = float(row["lon"])
        total += _haversine_km(current_lat, current_lon, lat, lon)
        current_lat = lat
        current_lon = lon
    return total


def evaluate_route_quality_vs_round_robin(db: Session, work_date: date) -> dict:
    assignment_rows = (
        db.query(
            DailyAssignment.visitor_id,
            DailyAssignment.route_order,
            Store.id.label("store_id"),
            Store.store_code,
            Store.lat,
            Store.lon,
        )
        .join(Store, Store.id == DailyAssignment.store_id)
        .filter(DailyAssignment.work_date == work_date)
        .all()
    )
    if not assignment_rows:
        return {
            "work_date": work_date.isoformat(),
            "baseline_km": 0.0,
            "current_km": 0.0,
            "improvement_pct": 0.0,
            "passes_gate": False,
        }

    visitor_contexts = get_active_visitor_day_contexts(db, work_date)
    context_by_visitor_id = {int(item["visitor_id"]): item for item in visitor_contexts}

    rows_by_visitor: dict[int, list[dict]] = {}
    for visitor_id, route_order, store_id, store_code, lat, lon in assignment_rows:
        rows_by_visitor.setdefault(int(visitor_id), []).append(
            {
                "route_order": route_order,
                "store_id": int(store_id),
                "store_code": store_code,
                "lat": float(lat),
                "lon": float(lon),
            }
        )

    current_total_km = 0.0
    for visitor_id, rows in rows_by_visitor.items():
        context = context_by_visitor_id.get(visitor_id)
        start_lat = context["start_lat"] if context else None
        start_lon = context["start_lon"] if context else None
        ordered_rows = sorted(
            rows,
            key=lambda row: (
                row["route_order"] is None,
                row["route_order"] if row["route_order"] is not None else 10**9,
                row["store_code"],
            ),
        )
        current_total_km += _calculate_path_length_for_rows(start_lat, start_lon, ordered_rows)

    all_stores = []
    for rows in rows_by_visitor.values():
        all_stores.extend(rows)

    all_stores.sort(key=lambda row: row["store_code"])
    visitor_ids = sorted(rows_by_visitor.keys())
    if not visitor_ids:
        visitor_ids = sorted(context_by_visitor_id.keys())

    baseline_assignments: dict[int, list[dict]] = {visitor_id: [] for visitor_id in visitor_ids}
    for idx, store in enumerate(all_stores):
        target_visitor_id = visitor_ids[idx % len(visitor_ids)]
        baseline_assignments[target_visitor_id].append(store)

    planner = routing_service.NearestNeighborRoutePlanner()
    baseline_total_km = 0.0
    for visitor_id, rows in baseline_assignments.items():
        if not rows:
            continue
        context = context_by_visitor_id.get(visitor_id)
        start_lat = context["start_lat"] if context else None
        start_lon = context["start_lon"] if context else None
        indexed_rows = list(enumerate(rows, start=1))
        stops = [
            {
                "assignment_id": index,
                "store_code": row["store_code"],
                "lat": row["lat"],
                "lon": row["lon"],
            }
            for index, row in indexed_rows
        ]
        planned = planner.plan_route(start_lat, start_lon, stops)
        planned_by_assignment_id = {item.assignment_id: item for item in planned}
        ordered_indexed_rows = sorted(
            indexed_rows,
            key=lambda row: planned_by_assignment_id.get(
                row[0],
                routing_service.RouteStop(assignment_id=0, route_order=10**9, route_distance_km=None),
            ).route_order,
        )
        ordered_rows = [row for _, row in ordered_indexed_rows]
        baseline_total_km += _calculate_path_length_for_rows(start_lat, start_lon, ordered_rows)

    improvement_pct = 0.0
    if baseline_total_km > 0:
        improvement_pct = ((baseline_total_km - current_total_km) / baseline_total_km) * 100.0

    return {
        "work_date": work_date.isoformat(),
        "baseline_km": round(baseline_total_km, 3),
        "current_km": round(current_total_km, 3),
        "improvement_pct": round(improvement_pct, 2),
        "passes_gate": bool(improvement_pct >= QUALITY_GATE_THRESHOLD_PCT),
    }
