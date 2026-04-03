from __future__ import annotations

from sqlalchemy.orm import Session

from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState


def get_store_by_id(db: Session, store_id: int) -> Store | None:
    return db.query(Store).filter(Store.id == store_id).first()


def list_active_stores(db: Session) -> list[Store]:
    return db.query(Store).filter(Store.is_active.is_(True)).all()


def list_stores_by_ids(db: Session, store_ids: list[int]) -> list[Store]:
    if not store_ids:
        return []
    return db.query(Store).filter(Store.id.in_(store_ids)).all()


def list_schedule_states_by_store_ids(
    db: Session, store_ids: list[int]
) -> list[StoreScheduleState]:
    if not store_ids:
        return []
    return (
        db.query(StoreScheduleState)
        .filter(StoreScheduleState.store_id.in_(store_ids))
        .all()
    )

