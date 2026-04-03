from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from server.app.enums.assignment_status import AssignmentStatus
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.store import Store
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile


def get_visit_by_assignment_id(db: Session, assignment_id: int) -> Visit | None:
    return db.query(Visit).filter(Visit.assignment_id == assignment_id).first()


def get_visit_by_id(db: Session, visit_id: int) -> Visit | None:
    return db.query(Visit).filter(Visit.id == visit_id).first()


def list_visit_ids_by_assignment_ids(db: Session, assignment_ids: list[int]) -> list[int]:
    if not assignment_ids:
        return []
    rows = db.query(Visit.id).filter(Visit.assignment_id.in_(assignment_ids)).all()
    return [int(visit_id) for (visit_id,) in rows]


def delete_visits_by_assignment_ids(db: Session, assignment_ids: list[int]) -> int:
    if not assignment_ids:
        return 0
    return (
        db.query(Visit)
        .filter(Visit.assignment_id.in_(assignment_ids))
        .delete(synchronize_session=False)
    )


def list_visit_events_for_store(db: Session, store_id: int) -> list[tuple]:
    return (
        db.query(Visit.visit_date, Visit.result)
        .filter(Visit.store_id == store_id)
        .order_by(Visit.visit_date, Visit.id)
        .all()
    )


def list_pending_published_assignments_without_visit(
    db: Session, work_date: date
) -> list[DailyAssignment]:
    return (
        db.query(DailyAssignment)
        .outerjoin(Visit, Visit.assignment_id == DailyAssignment.id)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.PUBLISHED.value,
            Visit.id.is_(None),
        )
        .all()
    )


def list_rows_for_visit_table(db: Session, work_date: date) -> list[tuple]:
    return (
        db.query(
            Visit.id.label("visit_id"),
            Visit.visit_date,
            VisitorProfile.visitor_code,
            Store.store_code,
            Visit.result,
            Visit.note,
        )
        .join(VisitorProfile, VisitorProfile.id == Visit.visitor_id)
        .join(Store, Store.id == Visit.store_id)
        .filter(Visit.visit_date == work_date)
        .order_by(VisitorProfile.visitor_code, Store.store_code)
        .all()
    )
