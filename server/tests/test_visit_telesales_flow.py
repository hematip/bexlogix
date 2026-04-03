from __future__ import annotations

from datetime import date

import pytest

from server.app.models.daily_assignment import DailyAssignment
from server.app.models.user import User
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import telesales_service, visit_service
from server.db.database import get_db_session


@pytest.mark.service
def test_visit_to_telesales_flow() -> None:
    db = get_db_session()
    try:
        work_date = date.today()
        assignment = (
            db.query(DailyAssignment)
            .outerjoin(Visit, Visit.assignment_id == DailyAssignment.id)
            .filter(
                DailyAssignment.work_date == work_date,
                DailyAssignment.assignment_status == "published",
                Visit.id.is_(None),
            )
            .order_by(DailyAssignment.id)
            .first()
        )
        if not assignment:
            pytest.skip("No published assignment without visit found. Run route generation first.")

        visitor_profile = (
            db.query(VisitorProfile)
            .filter(VisitorProfile.id == assignment.visitor_id)
            .first()
        )
        assert visitor_profile is not None

        visit = visit_service.submit_visit_result(
            db=db,
            assignment_id=assignment.id,
            visitor_user_id=visitor_profile.user_id,
            result="red",
            note="Store closed during visit window.",
        )
        assert visit.result == "red"

        pending = telesales_service.list_pending_followups(db, as_of_date=work_date)
        assert pending

        telesales_user = db.query(User).filter(User.username == "telesales1").first()
        assert telesales_user is not None

        followup_id = pending[0]["followup_id"]
        followup = telesales_service.submit_followup_result(
            db=db,
            followup_id=followup_id,
            telesales_user_id=telesales_user.id,
            contact_status="reached",
            result="sale_done",
            note="Order confirmed by phone.",
        )
        assert followup.result == "sale_done"
        assert followup.contact_status == "reached"
    finally:
        db.close()
