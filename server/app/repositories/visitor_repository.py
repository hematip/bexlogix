from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from server.app.enums.roles import UserRole
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.user import User
from server.app.models.visitor_profile import VisitorProfile


def get_profile_by_id(db: Session, visitor_id: int) -> VisitorProfile | None:
    return db.query(VisitorProfile).filter(VisitorProfile.id == visitor_id).first()


def get_profile_by_user_id(db: Session, user_id: int) -> VisitorProfile | None:
    return db.query(VisitorProfile).filter(VisitorProfile.user_id == user_id).first()


def list_visitor_code_rows_for_date(db: Session, work_date: date) -> list[tuple[int, str]]:
    return (
        db.query(VisitorProfile.id, VisitorProfile.visitor_code)
        .join(DailyAssignment, DailyAssignment.visitor_id == VisitorProfile.id)
        .filter(DailyAssignment.work_date == work_date)
        .distinct()
        .order_by(VisitorProfile.visitor_code)
        .all()
    )


def list_active_day_context_rows(db: Session, work_date: date) -> list[tuple]:
    return (
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


def get_start_point_for_date(
    db: Session,
    work_date: date,
    visitor_id: int,
) -> tuple[float | None, float | None]:
    daily_row = (
        db.query(DailyVisitorStatus)
        .filter(
            DailyVisitorStatus.visitor_id == visitor_id,
            DailyVisitorStatus.work_date == work_date,
        )
        .first()
    )
    if daily_row and daily_row.start_lat is not None and daily_row.start_lon is not None:
        return float(daily_row.start_lat), float(daily_row.start_lon)

    profile = get_profile_by_id(db, visitor_id)
    if not profile:
        return None, None
    if profile.default_start_lat is None or profile.default_start_lon is None:
        return None, None
    return float(profile.default_start_lat), float(profile.default_start_lon)


def count_daily_status_rows_for_date(db: Session, work_date: date) -> int:
    return (
        db.query(DailyVisitorStatus)
        .filter(DailyVisitorStatus.work_date == work_date)
        .count()
    )
