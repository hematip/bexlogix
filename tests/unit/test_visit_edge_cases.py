from __future__ import annotations

from datetime import date

import pytest

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.roles import UserRole
from server.app.enums.visit_result import VisitResult
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.store import Store
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.user import User
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import scheduling_service, visit_service


@pytest.mark.unit
def test_store_without_active_category_raises_clear_error() -> None:
    store = Store(
        store_code="STR-000",
        store_name="Store 000",
        region="مرکز",
        address="تهران",
        lat=35.7,
        lon=51.4,
        grade="A",
        has_confectionery=False,
        has_oil=False,
        has_pasta=False,
        is_active=True,
    )
    with pytest.raises(ValueError) as exc:
        scheduling_service.get_store_visit_interval_days(store)
    assert "هیچ دسته محصول فعالی" in str(exc.value)


@pytest.mark.unit
def test_red_visit_creates_followup_for_next_working_day(db) -> None:
    visitor_user = User(
        username="visitor-test",
        password_hash="hash",
        role=UserRole.VISITOR.value,
        is_active=True,
    )
    db.add(visitor_user)
    db.flush()

    visitor_profile = VisitorProfile(
        user_id=visitor_user.id,
        visitor_code="VIS-001",
        full_name="ویزیتور تست",
        default_start_lat=35.70,
        default_start_lon=51.40,
        default_capacity=30,
        is_active=True,
    )
    db.add(visitor_profile)
    db.flush()

    store = Store(
        store_code="STR-145",
        store_name="Zar Store 145",
        region="غرب",
        address="تهران",
        lat=35.64,
        lon=51.34,
        grade="A",
        has_confectionery=True,
        has_oil=False,
        has_pasta=False,
        is_active=True,
    )
    db.add(store)
    db.flush()

    friday = date(2026, 4, 3)
    assignment = DailyAssignment(
        work_date=friday,
        visitor_id=visitor_profile.id,
        store_id=store.id,
        assignment_status=AssignmentStatus.PUBLISHED.value,
        generated_by=None,
    )
    db.add(assignment)
    db.commit()

    visit_service.submit_visit_result(
        db=db,
        assignment_id=assignment.id,
        visitor_user_id=visitor_user.id,
        result=VisitResult.RED.value,
        note="دسترسی نبود",
    )

    followup = db.query(TelesalesFollowup).filter(TelesalesFollowup.visit_id.is_not(None)).first()
    assert followup is not None
    assert followup.followup_date >= friday

