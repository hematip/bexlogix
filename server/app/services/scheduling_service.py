from datetime import date, timedelta

from sqlalchemy.orm import Session

from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.enums.visit_result import VisitResult
from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.services.constants import (
    TELESALES_INVALID_DELAY_DAYS,
    TELESALES_NO_NEED_DELAY_DAYS,
    YELLOW_RETRY_DAYS,
)

CONFECTIONERY_OIL_INTERVALS = {
    "VIP": 6,
    "A+": 6,
    "A": 9,
    "B": 12,
    "C": 20,
}

PASTA_INTERVALS = {
    "VIP": 6,
    "A+": 6,
    "A": 10,
    "B": 8,
    "C": 8,
}


def _normalize_grade(grade: str) -> str:
    return str(grade or "").strip().upper()


def _get_or_create_state(db: Session, store_id: int, baseline_date: date) -> StoreScheduleState:
    state = (
        db.query(StoreScheduleState)
        .filter(StoreScheduleState.store_id == store_id)
        .first()
    )
    if state:
        return state

    state = StoreScheduleState(
        store_id=store_id,
        next_visit_date=baseline_date,
        overdue_days=0,
        in_telesales_queue=False,
    )
    db.add(state)
    db.flush()
    return state


def get_store_visit_interval_days(store: Store) -> int:
    grade = _normalize_grade(store.grade)
    if grade not in CONFECTIONERY_OIL_INTERVALS and grade not in PASTA_INTERVALS:
        raise ValueError(f"Unsupported store grade: {store.grade}")

    candidate_intervals: list[int] = []

    if store.has_confectionery:
        candidate_intervals.append(CONFECTIONERY_OIL_INTERVALS[grade])
    if store.has_oil:
        candidate_intervals.append(CONFECTIONERY_OIL_INTERVALS[grade])
    if store.has_pasta:
        candidate_intervals.append(PASTA_INTERVALS[grade])

    if not candidate_intervals:
        raise ValueError(
            f"Store '{store.store_code}' has no active product category for scheduling."
        )

    return min(candidate_intervals)


def compute_overdue_days(next_visit_date: date | None, target_date: date) -> int:
    if next_visit_date is None:
        return 0
    delta_days = (target_date - next_visit_date).days
    return max(delta_days, 0)


def ensure_store_schedule_state_rows(db: Session, target_date: date) -> int:
    created_count = 0

    stores = db.query(Store).filter(Store.is_active.is_(True)).all()
    try:
        for store in stores:
            existing_state = (
                db.query(StoreScheduleState)
                .filter(StoreScheduleState.store_id == store.id)
                .first()
            )
            if existing_state:
                continue

            state = StoreScheduleState(
                store_id=store.id,
                next_visit_date=target_date,
                overdue_days=0,
                in_telesales_queue=False,
            )
            db.add(state)
            created_count += 1

        db.commit()
        return created_count
    except Exception:
        db.rollback()
        raise


def refresh_overdue_days(db: Session, target_date: date) -> int:
    updated_count = 0
    try:
        states = (
            db.query(StoreScheduleState)
            .join(Store, Store.id == StoreScheduleState.store_id)
            .filter(Store.is_active.is_(True))
            .all()
        )

        for state in states:
            state.overdue_days = compute_overdue_days(state.next_visit_date, target_date)
            updated_count += 1

        db.commit()
        return updated_count
    except Exception:
        db.rollback()
        raise


def get_due_store_ids(db: Session, target_date: date) -> list[int]:
    ensure_store_schedule_state_rows(db, target_date)
    refresh_overdue_days(db, target_date)

    rows = (
        db.query(StoreScheduleState.store_id)
        .join(Store, Store.id == StoreScheduleState.store_id)
        .filter(
            Store.is_active.is_(True),
            StoreScheduleState.in_telesales_queue.is_(False),
            StoreScheduleState.next_visit_date.is_not(None),
            StoreScheduleState.next_visit_date <= target_date,
        )
        .all()
    )
    return [store_id for (store_id,) in rows]


def apply_visit_result_to_schedule(
    db: Session,
    store_id: int,
    visit_date: date,
    visit_result: str,
    commit: bool = True,
) -> StoreScheduleState:
    normalized_result = str(visit_result or "").strip().lower()
    allowed_results = {item.value for item in VisitResult}
    if normalized_result not in allowed_results:
        raise ValueError(f"Invalid visit result: {visit_result}")

    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise ValueError(f"Store id {store_id} not found.")

    try:
        state = _get_or_create_state(db, store_id, visit_date)
        state.last_visit_date = visit_date
        state.last_visit_result = normalized_result

        if normalized_result == VisitResult.GREEN.value:
            interval_days = get_store_visit_interval_days(store)
            state.next_visit_date = visit_date + timedelta(days=interval_days)
            state.in_telesales_queue = False
        elif normalized_result == VisitResult.YELLOW.value:
            state.next_visit_date = visit_date + timedelta(days=YELLOW_RETRY_DAYS)
            state.in_telesales_queue = False
        else:
            state.next_visit_date = None
            state.in_telesales_queue = True

        state.overdue_days = compute_overdue_days(state.next_visit_date, visit_date)

        if commit:
            db.commit()
        return state
    except Exception:
        if commit:
            db.rollback()
        raise


def apply_telesales_outcome_to_schedule(
    db: Session,
    store_id: int,
    followup_date: date,
    outcome: str,
    commit: bool = True,
) -> StoreScheduleState:
    normalized_outcome = str(outcome or "").strip().lower()
    allowed_outcomes = {item.value for item in TelesalesOutcome}
    if normalized_outcome not in allowed_outcomes:
        raise ValueError(f"Invalid telesales outcome: {outcome}")

    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise ValueError(f"Store id {store_id} not found.")

    try:
        state = _get_or_create_state(db, store_id, followup_date)
        state.last_visit_date = followup_date
        state.last_visit_result = normalized_outcome

        if normalized_outcome == TelesalesOutcome.SALE_DONE.value:
            interval_days = get_store_visit_interval_days(store)
            state.next_visit_date = followup_date + timedelta(days=interval_days)
            state.in_telesales_queue = False
        elif normalized_outcome == TelesalesOutcome.NO_NEED.value:
            state.next_visit_date = followup_date + timedelta(days=TELESALES_NO_NEED_DELAY_DAYS)
            state.in_telesales_queue = False
        elif normalized_outcome == TelesalesOutcome.POSTPONE.value:
            state.next_visit_date = None
            state.in_telesales_queue = True
        else:
            state.next_visit_date = followup_date + timedelta(days=TELESALES_INVALID_DELAY_DAYS)
            state.in_telesales_queue = False

        state.overdue_days = compute_overdue_days(state.next_visit_date, followup_date)

        if commit:
            db.commit()
        return state
    except Exception:
        if commit:
            db.rollback()
        raise
