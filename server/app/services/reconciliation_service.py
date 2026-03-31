from datetime import timedelta
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.visit import Visit
from server.app.services.constants import TELESALES_POSTPONE_DELAY_DAYS


def _normalize_store_ids(store_ids: Iterable[int] | None) -> list[int]:
    if store_ids is None:
        return []
    return sorted({int(store_id) for store_id in store_ids})


def repair_followup_store_mismatches(db: Session, commit: bool = False) -> dict:
    """
    Repair rule:
    Visit.store_id is source of truth for linked follow-up store_id.
    """
    rows = (
        db.query(TelesalesFollowup, Visit.store_id.label("visit_store_id"))
        .join(Visit, Visit.id == TelesalesFollowup.visit_id)
        .filter(TelesalesFollowup.store_id != Visit.store_id)
        .all()
    )

    updated_rows = []
    affected_store_ids: set[int] = set()

    for followup, visit_store_id in rows:
        old_store_id = int(followup.store_id)
        new_store_id = int(visit_store_id)
        followup.store_id = new_store_id
        updated_rows.append(
            {
                "followup_id": int(followup.id),
                "visit_id": int(followup.visit_id),
                "old_store_id": old_store_id,
                "new_store_id": new_store_id,
            }
        )
        affected_store_ids.add(old_store_id)
        affected_store_ids.add(new_store_id)

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {
        "updated_count": len(updated_rows),
        "updated_rows": updated_rows,
        "affected_store_ids": sorted(affected_store_ids),
    }


def repair_postpone_missing_open_followups(db: Session, commit: bool = False) -> dict:
    """
    Open follow-up in current MVP:
    result IS NULL.
    """
    postponed_rows = (
        db.query(
            TelesalesFollowup.id.label("followup_id"),
            TelesalesFollowup.visit_id,
            TelesalesFollowup.followup_date,
            TelesalesFollowup.created_by,
            Visit.store_id.label("visit_store_id"),
        )
        .join(Visit, Visit.id == TelesalesFollowup.visit_id)
        .filter(TelesalesFollowup.result == TelesalesOutcome.POSTPONE.value)
        .order_by(TelesalesFollowup.visit_id, TelesalesFollowup.followup_date, TelesalesFollowup.id)
        .all()
    )

    created_rows = []
    affected_store_ids: set[int] = set()

    for row in postponed_rows:
        existing_later_open = (
            db.query(TelesalesFollowup.id)
            .filter(
                TelesalesFollowup.visit_id == row.visit_id,
                TelesalesFollowup.result.is_(None),
                TelesalesFollowup.followup_date > row.followup_date,
            )
            .first()
        )
        if existing_later_open:
            continue

        new_followup = TelesalesFollowup(
            store_id=int(row.visit_store_id),
            visit_id=int(row.visit_id),
            followup_date=row.followup_date + timedelta(days=TELESALES_POSTPONE_DELAY_DAYS),
            created_by=row.created_by,
            contact_status=None,
            result=None,
            note=None,
        )
        db.add(new_followup)
        db.flush()

        created_rows.append(
            {
                "source_followup_id": int(row.followup_id),
                "new_followup_id": int(new_followup.id),
                "visit_id": int(row.visit_id),
                "store_id": int(row.visit_store_id),
                "new_followup_date": new_followup.followup_date.isoformat(),
            }
        )
        affected_store_ids.add(int(row.visit_store_id))

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {
        "created_count": len(created_rows),
        "created_rows": created_rows,
        "affected_store_ids": sorted(affected_store_ids),
    }


def reconcile_schedule_queue_flags(
    db: Session,
    store_ids: Iterable[int] | None = None,
    commit: bool = False,
) -> dict:
    """
    Keep StoreScheduleState.in_telesales_queue aligned with open follow-up reality.
    """
    scoped_store_ids = _normalize_store_ids(store_ids)

    pending_query = (
        db.query(TelesalesFollowup.store_id, func.count(TelesalesFollowup.id).label("pending_count"))
        .filter(TelesalesFollowup.result.is_(None))
    )
    if scoped_store_ids:
        pending_query = pending_query.filter(TelesalesFollowup.store_id.in_(scoped_store_ids))
    pending_rows = pending_query.group_by(TelesalesFollowup.store_id).all()
    pending_map = {int(store_id): int(pending_count) for store_id, pending_count in pending_rows}

    if scoped_store_ids:
        target_store_ids = set(scoped_store_ids) | set(pending_map.keys())
    else:
        existing_state_store_ids = {
            int(store_id)
            for (store_id,) in db.query(StoreScheduleState.store_id).all()
        }
        target_store_ids = existing_state_store_ids | set(pending_map.keys())

    if not target_store_ids:
        return {
            "updated_count": 0,
            "created_count": 0,
            "updated_rows": [],
            "created_rows": [],
        }

    state_rows = (
        db.query(StoreScheduleState)
        .filter(StoreScheduleState.store_id.in_(sorted(target_store_ids)))
        .all()
    )
    state_by_store_id = {int(row.store_id): row for row in state_rows}

    updated_rows = []
    created_rows = []

    for store_id in sorted(target_store_ids):
        expected_queue_flag = pending_map.get(store_id, 0) > 0
        state = state_by_store_id.get(store_id)

        if state is None:
            if not expected_queue_flag:
                continue
            state = StoreScheduleState(
                store_id=store_id,
                next_visit_date=None,
                overdue_days=0,
                in_telesales_queue=True,
            )
            db.add(state)
            db.flush()
            created_rows.append(
                {
                    "store_id": store_id,
                    "in_telesales_queue": True,
                }
            )
            continue

        current_queue_flag = bool(state.in_telesales_queue)
        if current_queue_flag != expected_queue_flag:
            state.in_telesales_queue = expected_queue_flag
            updated_rows.append(
                {
                    "store_id": store_id,
                    "old_in_telesales_queue": current_queue_flag,
                    "new_in_telesales_queue": expected_queue_flag,
                }
            )

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    return {
        "updated_count": len(updated_rows),
        "created_count": len(created_rows),
        "updated_rows": updated_rows,
        "created_rows": created_rows,
    }


def repair_known_integrity_blockers(db: Session) -> dict:
    """
    Runs targeted repairs for current known blocker types only.
    Idempotent and safe to rerun.
    """
    try:
        mismatch_result = repair_followup_store_mismatches(db=db, commit=False)
        postpone_result = repair_postpone_missing_open_followups(db=db, commit=False)

        affected_store_ids = sorted(
            set(mismatch_result["affected_store_ids"]) | set(postpone_result["affected_store_ids"])
        )

        queue_result = reconcile_schedule_queue_flags(
            db=db,
            store_ids=affected_store_ids,
            commit=False,
        )

        db.commit()
        return {
            "fixed_followup_store_mismatches": mismatch_result["updated_count"],
            "created_missing_postpone_open_followups": postpone_result["created_count"],
            "updated_schedule_queue_flags": queue_result["updated_count"],
            "created_schedule_state_rows": queue_result["created_count"],
            "affected_store_ids": affected_store_ids,
            "details": {
                "followup_store_mismatch_updates": mismatch_result["updated_rows"],
                "created_postpone_open_followups": postpone_result["created_rows"],
                "schedule_queue_updates": queue_result["updated_rows"],
                "schedule_rows_created": queue_result["created_rows"],
            },
        }
    except Exception:
        db.rollback()
        raise
