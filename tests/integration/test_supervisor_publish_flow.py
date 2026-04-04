from __future__ import annotations

from datetime import date

import pytest

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.roles import UserRole
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.store import Store
from server.app.models.user import User
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import assignment_service


@pytest.mark.integration
def test_supervisor_approval_required_before_manager_publish(db) -> None:
    manager = User(username="manager1", password_hash="h", role=UserRole.MANAGER.value, is_active=True)
    supervisor = User(username="supervisor1", password_hash="h", role=UserRole.SUPERVISOR.value, is_active=True)
    visitor_user = User(username="visitor1", password_hash="h", role=UserRole.VISITOR.value, is_active=True)
    db.add_all([manager, supervisor, visitor_user])
    db.flush()

    visitor_profile = VisitorProfile(
        user_id=visitor_user.id,
        visitor_code="VIS-001",
        full_name="ویزیتور یک",
        default_start_lat=35.70,
        default_start_lon=51.40,
        default_capacity=30,
        is_active=True,
    )
    store = Store(
        store_code="STR-001",
        store_name="Store 1",
        region="مرکز",
        address="تهران",
        lat=35.71,
        lon=51.41,
        grade="A",
        has_confectionery=True,
        has_oil=False,
        has_pasta=False,
        is_active=True,
    )
    db.add_all([visitor_profile, store])
    db.commit()

    work_date = date(2026, 4, 2)
    summary = assignment_service.generate_draft_assignments(
        db=db,
        work_date=work_date,
        manager_user_id=manager.id,
        replace_existing_draft=True,
    )
    assert summary["created_assignments"] == 1

    with pytest.raises(Exception):
        assignment_service.publish_assignments(
            db=db,
            work_date=work_date,
            manager_user_id=manager.id,
            include_draft_override=False,
        )

    approved_count = assignment_service.approve_visitor_route_for_work_date(
        db=db,
        work_date=work_date,
        visitor_id=visitor_profile.id,
        supervisor_user_id=supervisor.id,
    )
    assert approved_count == 1

    published_count = assignment_service.publish_assignments(
        db=db,
        work_date=work_date,
        manager_user_id=manager.id,
        include_draft_override=False,
    )
    assert published_count == 1

    saved = db.query(DailyAssignment).filter(DailyAssignment.work_date == work_date).first()
    assert saved is not None
    assert saved.assignment_status == AssignmentStatus.PUBLISHED.value

