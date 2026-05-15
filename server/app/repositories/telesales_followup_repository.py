# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from server.app.models.store import Store
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile


# Contract: get_followup_by_id executes one deterministic step in the workflow.
def get_followup_by_id(db: Session, followup_id: int) -> TelesalesFollowup | None:
    return db.query(TelesalesFollowup).filter(TelesalesFollowup.id == followup_id).first()


# Contract: get_open_followup_by_visit_id executes one deterministic step in the workflow.
def get_open_followup_by_visit_id(db: Session, visit_id: int) -> TelesalesFollowup | None:
    return (
        db.query(TelesalesFollowup)
        .filter(
            TelesalesFollowup.visit_id == visit_id,
            TelesalesFollowup.result.is_(None),
        )
        .first()
    )


# Contract: delete_followups_by_visit_ids executes one deterministic step in the workflow.
def delete_followups_by_visit_ids(db: Session, visit_ids: list[int]) -> int:
    if not visit_ids:
        return 0
    return (
        db.query(TelesalesFollowup)
        .filter(TelesalesFollowup.visit_id.in_(visit_ids))
        .delete(synchronize_session=False)
    )


# Contract: list_finalized_followup_events_for_store executes one deterministic step in the workflow.
def list_finalized_followup_events_for_store(db: Session, store_id: int) -> list[tuple]:
    return (
        db.query(TelesalesFollowup.followup_date, TelesalesFollowup.result)
        .filter(
            TelesalesFollowup.store_id == store_id,
            TelesalesFollowup.result.is_not(None),
        )
        .order_by(TelesalesFollowup.followup_date, TelesalesFollowup.id)
        .all()
    )


def list_finalized_followup_events_grouped_by_store(
    db: Session, store_ids: list[int]
) -> dict[int, list[tuple]]:
    """Batch counterpart to list_finalized_followup_events_for_store."""
    if not store_ids:
        return {}
    rows = (
        db.query(
            TelesalesFollowup.store_id,
            TelesalesFollowup.followup_date,
            TelesalesFollowup.result,
            TelesalesFollowup.id,
        )
        .filter(
            TelesalesFollowup.store_id.in_(store_ids),
            TelesalesFollowup.result.is_not(None),
        )
        .order_by(TelesalesFollowup.store_id, TelesalesFollowup.followup_date, TelesalesFollowup.id)
        .all()
    )
    grouped: dict[int, list[tuple]] = {int(sid): [] for sid in store_ids}
    for store_id, followup_date, result, _row_id in rows:
        grouped.setdefault(int(store_id), []).append((followup_date, result))
    return grouped


# Contract: list_pending_followup_rows executes one deterministic step in the workflow.
def list_pending_followup_rows(db: Session, as_of_date: date | None = None) -> list[tuple]:
    query = (
        db.query(TelesalesFollowup, Store, Visit, VisitorProfile)
        .join(Store, Store.id == TelesalesFollowup.store_id)
        .join(Visit, Visit.id == TelesalesFollowup.visit_id)
        .outerjoin(VisitorProfile, VisitorProfile.id == Visit.visitor_id)
        .filter(TelesalesFollowup.result.is_(None))
    )
    if as_of_date is not None:
        query = query.filter(TelesalesFollowup.followup_date <= as_of_date)
    return query.order_by(TelesalesFollowup.followup_date, Store.store_code).all()
