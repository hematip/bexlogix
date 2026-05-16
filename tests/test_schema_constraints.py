"""Tests that the production-readiness DB invariants are actually enforced."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.visit_result import VisitResult
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.daily_visitor_status import DailyVisitorStatus
from server.app.models.store import Store
from server.app.models.store_schedule_state import StoreScheduleState
from server.app.models.user import User
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile


@pytest.fixture
def base_records(db_session):
    """Insert one user, one visitor profile, and one store. Return their ids."""
    user = User(
        username="u1",
        password_hash="x",
        role="visitor",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    profile = VisitorProfile(
        user_id=user.id,
        visitor_code="VIS-001",
        full_name="V1",
        default_start_lat=35.7,
        default_start_lon=51.3,
        default_capacity=30,
        is_active=True,
    )
    db_session.add(profile)
    db_session.flush()

    store = Store(
        store_code="STR-001",
        store_name="S1",
        region="مرکز",
        lat=35.7,
        lon=51.3,
        grade="A+",
        has_confectionery=True,
        has_oil=False,
        has_pasta=False,
    )
    db_session.add(store)
    db_session.flush()
    db_session.commit()

    return {"user_id": user.id, "visitor_id": profile.id, "store_id": store.id}


class TestDailyAssignmentUniqueness:
    def test_same_store_same_day_to_two_visitors_is_blocked(self, db_session, base_records):
        a1 = DailyAssignment(
            work_date=date(2026, 5, 15),
            visitor_id=base_records["visitor_id"],
            store_id=base_records["store_id"],
            assignment_status=AssignmentStatus.DRAFT.value,
        )
        db_session.add(a1)
        db_session.commit()

        a2 = DailyAssignment(
            work_date=date(2026, 5, 15),
            visitor_id=base_records["visitor_id"],
            store_id=base_records["store_id"],
            assignment_status=AssignmentStatus.DRAFT.value,
        )
        db_session.add(a2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()

    def test_same_store_different_day_is_allowed(self, db_session, base_records):
        for d in [date(2026, 5, 15), date(2026, 5, 16)]:
            db_session.add(DailyAssignment(
                work_date=d,
                visitor_id=base_records["visitor_id"],
                store_id=base_records["store_id"],
                assignment_status=AssignmentStatus.DRAFT.value,
            ))
        db_session.commit()
        assert db_session.query(DailyAssignment).count() == 2


class TestVisitUniqueness:
    def test_one_visit_per_assignment(self, db_session, base_records):
        a = DailyAssignment(
            work_date=date(2026, 5, 15),
            visitor_id=base_records["visitor_id"],
            store_id=base_records["store_id"],
            assignment_status=AssignmentStatus.PUBLISHED.value,
        )
        db_session.add(a)
        db_session.flush()

        db_session.add(Visit(
            assignment_id=a.id,
            store_id=base_records["store_id"],
            visitor_id=base_records["visitor_id"],
            visit_date=date(2026, 5, 15),
            result=VisitResult.GREEN.value,
        ))
        db_session.commit()

        db_session.add(Visit(
            assignment_id=a.id,
            store_id=base_records["store_id"],
            visitor_id=base_records["visitor_id"],
            visit_date=date(2026, 5, 15),
            result=VisitResult.YELLOW.value,
        ))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestDailyVisitorStatusUniqueness:
    def test_one_status_row_per_visitor_per_day(self, db_session, base_records):
        db_session.add(DailyVisitorStatus(
            visitor_id=base_records["visitor_id"],
            work_date=date(2026, 5, 15),
            capacity=30,
            is_active_today=True,
        ))
        db_session.commit()
        db_session.add(DailyVisitorStatus(
            visitor_id=base_records["visitor_id"],
            work_date=date(2026, 5, 15),
            capacity=25,
            is_active_today=True,
        ))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestStoreScheduleStateUniqueness:
    def test_one_schedule_state_per_store(self, db_session, base_records):
        db_session.add(StoreScheduleState(
            store_id=base_records["store_id"],
            next_visit_date=date(2026, 5, 15),
            overdue_days=0,
            in_telesales_queue=False,
        ))
        db_session.commit()
        db_session.add(StoreScheduleState(
            store_id=base_records["store_id"],
            next_visit_date=date(2026, 5, 16),
            overdue_days=0,
            in_telesales_queue=False,
        ))
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()
