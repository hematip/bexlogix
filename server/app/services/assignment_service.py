# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from datetime import date, datetime, timezone
from math import asin, cos, radians, sin, sqrt

from sqlalchemy.orm import Session

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.roles import UserRole
from server.app.errors import (
    DomainError,
    PermissionError as AppPermissionError,
    ValidationError,
    err,
)
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.repositories import (
    assignment_repository,
    store_repository,
    telesales_followup_repository,
    user_repository,
    visit_repository,
    visitor_repository,
)
from server.app.services import routing_service, scheduling_service

QUALITY_GATE_THRESHOLD_PCT = 20.0
DISTANCE_BALANCE_TOLERANCE_PCT = (
    20.0  # Max allowed deviation from mean visitor distance.
)


# Contract: _assert_manager_user executes one deterministic step in the workflow.
def _assert_manager_user(db: Session, manager_user_id: int) -> None:
    user = user_repository.get_user_by_id(db, manager_user_id)
    if not user:
        raise ValidationError(err("manager_user_not_found"))
    if user.role != UserRole.MANAGER.value:
        raise AppPermissionError(err("manager_only_generate_publish"))


def _assert_supervisor_user(db: Session, supervisor_user_id: int) -> None:
    # FIX: [UX-10] Explicit permission boundary for supervisor approval workflow.
    user = user_repository.get_user_by_id(db, supervisor_user_id)
    if not user:
        raise ValidationError("کاربر سرپرست معتبر پیدا نشد.")
    if user.role != UserRole.SUPERVISOR.value:
        raise AppPermissionError(err("supervisor_only_approve"))


# Contract: _haversine_km executes one deterministic step in the workflow.
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


# Contract: get_active_visitor_day_contexts executes one deterministic step in the workflow.
def get_active_visitor_day_contexts(db: Session, work_date: date) -> list[dict]:
    rows = visitor_repository.list_active_day_context_rows(db=db, work_date=work_date)

    contexts: list[dict] = []
    for row in rows:
        if not row.user_is_active or not row.profile_is_active:
            continue

        is_active_today = (
            True if row.is_active_today is None else bool(row.is_active_today)
        )
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

        start_lat = (
            row.start_lat if row.start_lat is not None else row.default_start_lat
        )
        start_lon = (
            row.start_lon if row.start_lon is not None else row.default_start_lon
        )

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


# Contract: _get_due_stores_sorted executes one deterministic step in the workflow.
def _get_due_stores_sorted(db: Session, work_date: date) -> list[Store]:
    due_store_ids = scheduling_service.get_due_store_ids_readonly(db, work_date)
    if not due_store_ids:
        return []

    stores = store_repository.list_stores_by_ids(db=db, store_ids=due_store_ids)
    states = store_repository.list_schedule_states_by_store_ids(
        db=db, store_ids=due_store_ids
    )
    states_by_store_id = {state.store_id: state for state in states}

    # Contract: sort_key executes one deterministic step in the workflow.
    def sort_key(store: Store):
        state = states_by_store_id.get(store.id)
        overdue_days = state.overdue_days if state else 0
        next_visit_date = (
            state.next_visit_date if state and state.next_visit_date else date.min
        )
        interval_days = scheduling_service.get_store_visit_interval_days(store)
        return (-overdue_days, interval_days, next_visit_date, store.store_code)

    return sorted(stores, key=sort_key)


# Contract: _delete_existing_drafts executes one deterministic step in the workflow.
def _delete_existing_drafts(db: Session, work_date: date) -> int:
    return assignment_repository.delete_draft_assignments_for_date(
        db=db, work_date=work_date
    )


# Contract: _select_closest_store_for_visitor executes one deterministic step in the workflow.
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


# Contract: _geo_capacity_allocate_stores executes one deterministic step in the workflow.
def _geo_capacity_allocate_stores(
    visitors: list[dict], due_stores: list[Store]
) -> dict[int, list[Store]]:
    allocations: dict[int, list[Store]] = {
        visitor["visitor_id"]: [] for visitor in visitors
    }
    if not visitors or not due_stores:
        return allocations

    visitor_state = {
        visitor["visitor_id"]: {
            "remaining_capacity": int(visitor["capacity"]),
            "assigned_count": 0,
            "current_lat": (
                float(visitor["start_lat"])
                if visitor["start_lat"] is not None
                else None
            ),
            "current_lon": (
                float(visitor["start_lon"])
                if visitor["start_lon"] is not None
                else None
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
            nearest = _select_closest_store_for_visitor(
                state, unassigned_stores, store_priority
            )
            if nearest is None:
                continue
            nearest_store, distance = nearest
            candidate_pairs.append((distance, visitor_id, nearest_store))

        if candidate_pairs:
            candidate_pairs.sort(
                key=lambda item: (item[0], item[1], item[2].store_code)
            )
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


# Contract: _geo_capacity_allocate_stores_balanced allocates stores with distance fairness.
# Strategy: round-robin where the visitor with the LOWEST cumulative travel distance picks
# their nearest unassigned store. When a visitor exceeds the tolerance threshold above the
# current mean, they are temporarily skipped (soft-capped) until others catch up.
# This naturally equalizes total travel distance across visitors even at the cost of
# slightly unequal store counts.
def _geo_capacity_allocate_stores_balanced(
    visitors: list[dict],
    due_stores: list[Store],
) -> dict[int, list[Store]]:
    allocations: dict[int, list[Store]] = {
        visitor["visitor_id"]: [] for visitor in visitors
    }
    if not visitors or not due_stores:
        return allocations

    tolerance = DISTANCE_BALANCE_TOLERANCE_PCT / 100.0  # 0.20

    # When balancing, add a 20% capacity headroom so that visitors with shorter routes
    # can absorb extra stores from those with longer routes.
    total_stores = len(due_stores)
    total_capacity_raw = sum(int(v["capacity"]) for v in visitors)
    headroom_factor = 1.2 if total_capacity_raw <= total_stores else 1.0

    visitor_state = {
        visitor["visitor_id"]: {
            "remaining_capacity": min(
                int(int(visitor["capacity"]) * headroom_factor),
                total_stores,  # Never exceed total stores as upper bound.
            ),
            "assigned_count": 0,
            "cumulative_km": 0.0,
            "current_lat": (
                float(visitor["start_lat"])
                if visitor["start_lat"] is not None
                else None
            ),
            "current_lon": (
                float(visitor["start_lon"])
                if visitor["start_lon"] is not None
                else None
            ),
        }
        for visitor in visitors
    }

    store_priority = {store.id: index for index, store in enumerate(due_stores)}
    unassigned_stores = due_stores.copy()

    while unassigned_stores:
        # Find active visitors (still have capacity).
        active_visitors = [
            visitor
            for visitor in visitors
            if visitor_state[visitor["visitor_id"]]["remaining_capacity"] > 0
        ]
        if not active_visitors:
            break

        # Compute mean cumulative distance across ALL active visitors.
        active_distances = [
            visitor_state[v["visitor_id"]]["cumulative_km"] for v in active_visitors
        ]
        mean_km = (
            sum(active_distances) / len(active_distances) if active_distances else 0.0
        )

        # Soft-cap: skip visitors whose cumulative_km > mean * (1 + tolerance),
        # unless everyone exceeds the cap (then allow all).
        if mean_km > 0.5:  # Only apply cap when meaningful distances have accumulated.
            eligible_visitors = [
                v
                for v in active_visitors
                if visitor_state[v["visitor_id"]]["cumulative_km"]
                <= mean_km * (1.0 + tolerance)
            ]
            if not eligible_visitors:
                eligible_visitors = active_visitors
        else:
            eligible_visitors = active_visitors

        # Among eligible, pick the one with the lowest cumulative distance.
        eligible_visitors.sort(
            key=lambda v: (
                visitor_state[v["visitor_id"]]["cumulative_km"],
                visitor_state[v["visitor_id"]]["assigned_count"],
                v["visitor_id"],
            )
        )
        selected_visitor = eligible_visitors[0]
        selected_vid = selected_visitor["visitor_id"]
        state = visitor_state[selected_vid]

        # Find nearest store for this visitor.
        if state["current_lat"] is not None and state["current_lon"] is not None:
            nearest = _select_closest_store_for_visitor(
                state, unassigned_stores, store_priority
            )
            if nearest is not None:
                selected_store, step_km = nearest
            else:
                selected_store = unassigned_stores[0]
                step_km = 0.0
        else:
            selected_store = unassigned_stores[0]
            step_km = 0.0

        allocations[selected_vid].append(selected_store)
        state["remaining_capacity"] -= 1
        state["assigned_count"] += 1
        state["cumulative_km"] += step_km
        state["current_lat"] = float(selected_store.lat)
        state["current_lon"] = float(selected_store.lon)
        unassigned_stores.remove(selected_store)

    # Phase 2: Post-allocation swap rebalancing.
    # Move stores from the highest-distance visitor to the lowest-distance visitor
    # when doing so reduces max deviation.
    visitor_by_id = {v["visitor_id"]: v for v in visitors}
    max_swap_iterations = len(due_stores) * 2  # Safety limit.
    for _ in range(max_swap_iterations):
        # Recalculate distances.
        visitor_km: dict[int, float] = {}
        for vid, store_list in allocations.items():
            v = visitor_by_id[vid]
            total = 0.0
            lat = float(v["start_lat"]) if v["start_lat"] is not None else None
            lon = float(v["start_lon"]) if v["start_lon"] is not None else None
            for store in store_list:
                if lat is not None and lon is not None:
                    total += _haversine_km(lat, lon, float(store.lat), float(store.lon))
                lat = float(store.lat)
                lon = float(store.lon)
            visitor_km[vid] = total

        if not visitor_km:
            break
        values = list(visitor_km.values())
        mean_km_post = sum(values) / len(values)
        if mean_km_post < 0.1:
            break

        max_vid = max(visitor_km, key=visitor_km.get)
        min_vid = min(visitor_km, key=visitor_km.get)
        if max_vid == min_vid:
            break

        current_deviation = max(abs(v - mean_km_post) / mean_km_post for v in values)
        if current_deviation <= tolerance:
            break  # Already within tolerance.

        # Try to move the last store from max_vid to min_vid.
        if not allocations[max_vid]:
            break
        candidate_store = allocations[max_vid][-1]

        # Simulate the swap.
        test_max_stores = allocations[max_vid][:-1]
        test_min_stores = allocations[min_vid] + [candidate_store]

        def _calc_path(vid, store_list):
            v = visitor_by_id[vid]
            total = 0.0
            lat = float(v["start_lat"]) if v["start_lat"] is not None else None
            lon = float(v["start_lon"]) if v["start_lon"] is not None else None
            for store in store_list:
                if lat is not None and lon is not None:
                    total += _haversine_km(lat, lon, float(store.lat), float(store.lon))
                lat = float(store.lat)
                lon = float(store.lon)
            return total

        new_max_km = _calc_path(max_vid, test_max_stores)
        new_min_km = _calc_path(min_vid, test_min_stores)

        # Accept swap only if it reduces the spread between max and min.
        old_spread = visitor_km[max_vid] - visitor_km[min_vid]
        new_spread = abs(new_max_km - new_min_km)
        if new_spread >= old_spread:
            break  # No improvement, stop.

        allocations[max_vid] = test_max_stores
        allocations[min_vid] = test_min_stores

    return allocations


# Contract: compute_distance_fairness_metrics returns per-visitor distance stats.
def compute_distance_fairness_metrics(
    visitors: list[dict],
    allocations: dict[int, list[Store]],
) -> dict:
    visitor_distances: dict[int, float] = {}
    for visitor in visitors:
        vid = visitor["visitor_id"]
        stores = allocations.get(vid, [])
        if not stores:
            visitor_distances[vid] = 0.0
            continue
        total = 0.0
        lat = float(visitor["start_lat"]) if visitor["start_lat"] is not None else None
        lon = float(visitor["start_lon"]) if visitor["start_lon"] is not None else None
        for store in stores:
            if lat is not None and lon is not None:
                total += _haversine_km(lat, lon, float(store.lat), float(store.lon))
            lat = float(store.lat)
            lon = float(store.lon)
        visitor_distances[vid] = round(total, 3)

    if not visitor_distances:
        return {
            "mean_km": 0.0,
            "min_km": 0.0,
            "max_km": 0.0,
            "std_dev_km": 0.0,
            "max_deviation_pct": 0.0,
            "is_balanced": True,
            "per_visitor": {},
        }

    values = list(visitor_distances.values())
    mean_km = sum(values) / len(values)
    min_km = min(values)
    max_km = max(values)
    variance = sum((v - mean_km) ** 2 for v in values) / len(values) if values else 0.0
    std_dev_km = variance**0.5

    max_deviation_pct = 0.0
    if mean_km > 0:
        max_deviation_pct = max(abs(v - mean_km) / mean_km * 100.0 for v in values)

    return {
        "mean_km": round(mean_km, 3),
        "min_km": round(min_km, 3),
        "max_km": round(max_km, 3),
        "std_dev_km": round(std_dev_km, 3),
        "max_deviation_pct": round(max_deviation_pct, 2),
        "is_balanced": bool(max_deviation_pct <= DISTANCE_BALANCE_TOLERANCE_PCT),
        "per_visitor": visitor_distances,
    }


# Contract: generate_draft_assignments executes one deterministic step in the workflow.
def generate_draft_assignments(
    db: Session,
    work_date: date,
    manager_user_id: int,
    replace_existing_draft: bool = True,
    balance_distance: bool = False,
) -> dict:
    _assert_manager_user(db, manager_user_id)
    scheduling_service.prepare_schedule_state_for_date(
        db=db, target_date=work_date
    )  # FIX: [ARCH-03] Move schedule-state writes to manager pipeline path.

    existing_non_draft_count = (
        assignment_repository.count_non_draft_assignments_for_date(
            db=db,
            work_date=work_date,
        )
    )
    if existing_non_draft_count > 0:
        raise DomainError(err("non_draft_exists_block_regen"))

    if replace_existing_draft:
        _delete_existing_drafts(db, work_date)
    else:
        existing_draft_count = assignment_repository.count_draft_assignments_for_date(
            db=db,
            work_date=work_date,
        )
        if existing_draft_count > 0:
            raise DomainError(err("draft_exists_for_date"))

    visitors = get_active_visitor_day_contexts(db, work_date)
    due_stores = _get_due_stores_sorted(db, work_date)

    if balance_distance:
        allocations = _geo_capacity_allocate_stores_balanced(
            visitors=visitors,
            due_stores=due_stores,
        )
    else:
        allocations = _geo_capacity_allocate_stores(
            visitors=visitors,
            due_stores=due_stores,
        )

    # Compute fairness metrics regardless of allocation mode.
    fairness = compute_distance_fairness_metrics(
        visitors=visitors,
        allocations=allocations,
    )

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

    unassigned_store_ids = [
        store.id for store in due_stores if store.id not in assigned_store_ids
    ]
    return {
        "work_date": work_date.isoformat(),
        "active_visitors": len(visitors),
        "due_stores": len(due_stores),
        "created_assignments": created_count,
        "unassigned_due_stores": len(unassigned_store_ids),
        "unassigned_store_ids": unassigned_store_ids,
        "balance_distance": bool(balance_distance),
        "fairness": fairness,
    }


# Contract: get_unassigned_due_store_ids executes one deterministic step in the workflow.
def get_unassigned_due_store_ids(db: Session, work_date: date) -> list[int]:
    due_store_ids = set(scheduling_service.get_due_store_ids_readonly(db, work_date))
    if not due_store_ids:
        return []

    assigned_store_ids = set(
        assignment_repository.list_assigned_store_ids_for_date(
            db=db, work_date=work_date
        )
    )
    return sorted(due_store_ids - assigned_store_ids)


# Contract: publish_assignments executes one deterministic step in the workflow.
def publish_assignments(
    db: Session,
    work_date: date,
    manager_user_id: int,
    include_draft_override: bool = False,
) -> int:
    # FIX: [UX-10] Publish defaults to supervisor_approved; manager can override to include draft.
    _assert_manager_user(db, manager_user_id)

    publishable_assignments = assignment_repository.list_assignments_for_publish(
        db=db,
        work_date=work_date,
        include_draft_override=include_draft_override,
    )
    if not publishable_assignments:
        raise DomainError(
            err("no_draft_assignments")
            if include_draft_override
            else err("no_supervisor_approved_to_publish")
        )

    try:
        publish_time = datetime.now(timezone.utc)
        for assignment in publishable_assignments:
            assignment.assignment_status = AssignmentStatus.PUBLISHED.value
            assignment.published_at = publish_time

        db.commit()
        return len(publishable_assignments)
    except Exception:
        db.rollback()
        raise


def approve_visitor_route_for_work_date(
    db: Session,
    work_date: date,
    visitor_id: int,
    supervisor_user_id: int,
) -> int:
    # FIX: [UX-10] Supervisor can move draft assignments to supervisor_approved per visitor/date.
    _assert_supervisor_user(db=db, supervisor_user_id=supervisor_user_id)
    draft_assignments = assignment_repository.list_assignments_for_visitor_date(
        db=db,
        work_date=work_date,
        visitor_id=visitor_id,
        status=AssignmentStatus.DRAFT.value,
    )
    if not draft_assignments:
        raise DomainError(err("no_draft_for_visitor_approve"))

    try:
        for assignment in draft_assignments:
            assignment.assignment_status = AssignmentStatus.SUPERVISOR_APPROVED.value
        db.commit()
        return len(draft_assignments)
    except Exception:
        db.rollback()
        raise


# Contract: get_work_date_operational_snapshot executes one deterministic step in the workflow.
def get_work_date_operational_snapshot(db: Session, work_date: date) -> dict:
    assignment_count = assignment_repository.count_assignments_for_date(
        db=db, work_date=work_date
    )
    status_counts = assignment_repository.count_assignments_grouped_by_status(
        db=db,
        work_date=work_date,
    )
    draft_count = int(status_counts.get(AssignmentStatus.DRAFT.value, 0))
    supervisor_approved_count = int(
        status_counts.get(AssignmentStatus.SUPERVISOR_APPROVED.value, 0)
    )
    published_count = int(status_counts.get(AssignmentStatus.PUBLISHED.value, 0))
    completed_count = int(status_counts.get(AssignmentStatus.COMPLETED.value, 0))
    skipped_count = int(status_counts.get(AssignmentStatus.SKIPPED.value, 0))
    non_draft_count = assignment_repository.count_non_draft_assignments_for_date(
        db=db,
        work_date=work_date,
    )
    visit_count = assignment_repository.count_visits_linked_to_assignment_date(
        db=db,
        work_date=work_date,
    )
    followup_count = assignment_repository.count_followups_linked_to_assignment_date(
        db=db,
        work_date=work_date,
    )

    return {
        "work_date": work_date.isoformat(),
        "assignment_count": int(assignment_count),
        "draft_count": draft_count,
        "supervisor_approved_count": supervisor_approved_count,
        "published_count": published_count,
        "completed_count": completed_count,
        "skipped_count": skipped_count,
        "non_draft_count": int(non_draft_count),
        "visit_count": int(visit_count),
        "followup_count": int(followup_count),
        "is_locked": bool(
            published_count > 0
            or completed_count > 0
            or skipped_count > 0
            or visit_count > 0
            or followup_count > 0
        ),
    }


def reset_draft_assignments_for_date(
    db: Session,
    work_date: date,
    manager_user_id: int,
) -> dict:
    # FIX: [UX-05] Soft reset to only remove draft assignments when no visit/follow-up exists.
    _assert_manager_user(db=db, manager_user_id=manager_user_id)
    snapshot = get_work_date_operational_snapshot(db=db, work_date=work_date)
    if snapshot["visit_count"] > 0 or snapshot["followup_count"] > 0:
        raise DomainError(
            "برای این تاریخ ویزیت یا پیگیری ثبت شده است؛ فقط پاک‌سازی کامل مجاز است."
        )

    deleted_count = assignment_repository.delete_draft_assignments_for_date(
        db=db, work_date=work_date
    )
    db.commit()
    return {
        "work_date": work_date.isoformat(),
        "deleted_draft_count": int(deleted_count),
    }


# Contract: _rebuild_store_schedule_state_from_history executes one deterministic step in the workflow.
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

    visit_rows = visit_repository.list_visit_events_for_store(db=db, store_id=store_id)
    for visit_date, result in visit_rows:
        events.append((visit_date, 0, "visit", result))

    followup_rows = (
        telesales_followup_repository.list_finalized_followup_events_for_store(
            db=db,
            store_id=store_id,
        )
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


# Contract: flush_work_date_operational_data executes one deterministic step in the workflow.
def flush_work_date_operational_data(
    db: Session, work_date: date, manager_user_id: int
) -> dict:
    _assert_manager_user(db, manager_user_id)

    assignment_rows = assignment_repository.list_assignment_ids_and_store_ids_for_date(
        db=db,
        work_date=work_date,
    )
    assignment_ids = [int(assignment_id) for assignment_id, _ in assignment_rows]
    affected_store_ids = {int(store_id) for _, store_id in assignment_rows}

    visit_ids = visit_repository.list_visit_ids_by_assignment_ids(
        db=db,
        assignment_ids=assignment_ids,
    )

    followup_deleted = telesales_followup_repository.delete_followups_by_visit_ids(
        db=db,
        visit_ids=visit_ids,
    )

    visits_deleted = visit_repository.delete_visits_by_assignment_ids(
        db=db,
        assignment_ids=assignment_ids,
    )

    assignments_deleted = assignment_repository.delete_assignments_for_date(
        db=db,
        work_date=work_date,
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


# Contract: _calculate_path_length_for_rows executes one deterministic step in the workflow.
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


# Contract: evaluate_route_quality_vs_round_robin executes one deterministic step in the workflow.
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
            "comparable": False,
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
        current_total_km += _calculate_path_length_for_rows(
            start_lat, start_lon, ordered_rows
        )

    all_stores = []
    for rows in rows_by_visitor.values():
        all_stores.extend(rows)

    all_stores.sort(key=lambda row: row["store_code"])
    visitor_ids = sorted(rows_by_visitor.keys())
    if not visitor_ids:
        visitor_ids = sorted(context_by_visitor_id.keys())

    baseline_assignments: dict[int, list[dict]] = {
        visitor_id: [] for visitor_id in visitor_ids
    }
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
                routing_service.RouteStop(
                    assignment_id=0, route_order=10**9, route_distance_km=None
                ),
            ).route_order,
        )
        ordered_rows = [row for _, row in ordered_indexed_rows]
        baseline_total_km += _calculate_path_length_for_rows(
            start_lat, start_lon, ordered_rows
        )

    improvement_pct = 0.0
    if baseline_total_km > 0:
        improvement_pct = (
            (baseline_total_km - current_total_km) / baseline_total_km
        ) * 100.0

    return {
        "work_date": work_date.isoformat(),
        "baseline_km": round(baseline_total_km, 3),
        "current_km": round(current_total_km, 3),
        "improvement_pct": round(improvement_pct, 2),
        "comparable": bool(baseline_total_km > 0),
        "passes_gate": bool(improvement_pct >= QUALITY_GATE_THRESHOLD_PCT),
    }
