from datetime import date

from server.app.models.daily_assignment import DailyAssignment
from server.app.models.user import User
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import telesales_service, visit_service
from server.db.database import get_db_session


def main():
    db = get_db_session()
    try:
        work_date = date(2026, 3, 31)

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
            print("No published assignment without visit found. Run test_generate_routes first.")
            return

        visitor_profile = (
            db.query(VisitorProfile)
            .filter(VisitorProfile.id == assignment.visitor_id)
            .first()
        )
        if not visitor_profile:
            raise ValueError("Visitor profile not found for assignment.")

        visit = visit_service.submit_visit_result(
            db=db,
            assignment_id=assignment.id,
            visitor_user_id=visitor_profile.user_id,
            result="red",
            note="Store closed during visit window.",
        )
        print(f"Visit created with id {visit.id} and result {visit.result}.")

        pending = telesales_service.list_pending_followups(db, as_of_date=work_date)
        if not pending:
            print("No pending followups found after red visit.")
            return

        telesales_user = db.query(User).filter(User.username == "telesales1").first()
        if not telesales_user:
            raise ValueError("telesales1 user not found.")

        followup_id = pending[0]["followup_id"]
        followup = telesales_service.submit_followup_result(
            db=db,
            followup_id=followup_id,
            telesales_user_id=telesales_user.id,
            contact_status="reached",
            result="sale_done",
            note="Order confirmed by phone.",
        )
        print(
            f"Followup {followup.id} saved. contact_status={followup.contact_status}, "
            f"result={followup.result}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
