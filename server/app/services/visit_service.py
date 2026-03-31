from datetime import date, datetime

from sqlalchemy.orm import Session

from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.roles import UserRole
from server.app.enums.visit_result import VisitResult
from server.app.models.daily_assignment import DailyAssignment
from server.app.models.user import User
from server.app.models.visit import Visit
from server.app.models.visitor_profile import VisitorProfile
from server.app.services import scheduling_service, telesales_service


def _assert_manager_user(db: Session, user_id: int) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User id {user_id} not found.")
    if user.role != UserRole.MANAGER.value:
        raise ValueError("Only manager users can finalize unsubmitted assignments.")


def submit_visit_result(
    db: Session,
    assignment_id: int,
    visitor_user_id: int,
    result: str,
    note: str | None,
    submitted_at: datetime | None = None,
) -> Visit:
    normalized_result = str(result or "").strip().lower()
    allowed_results = {item.value for item in VisitResult}
    if normalized_result not in allowed_results:
        raise ValueError(f"Invalid visit result: {result}")

    assignment = (
        db.query(DailyAssignment)
        .filter(DailyAssignment.id == assignment_id)
        .first()
    )
    if not assignment:
        raise ValueError(f"Assignment id {assignment_id} not found.")
    if assignment.assignment_status != AssignmentStatus.PUBLISHED.value:
        raise ValueError("Visit submission is allowed only for published assignments.")

    visitor_profile = (
        db.query(VisitorProfile)
        .filter(VisitorProfile.id == assignment.visitor_id)
        .first()
    )
    if not visitor_profile:
        raise ValueError("Visitor profile linked to assignment was not found.")
    if visitor_profile.user_id != visitor_user_id:
        raise ValueError("You can only submit visit results for your own assignments.")

    existing_visit = (
        db.query(Visit)
        .filter(Visit.assignment_id == assignment.id)
        .first()
    )
    if existing_visit:
        raise ValueError("Visit result is already submitted for this assignment.")

    visit_note = str(note or "").strip() or None
    visit_date = assignment.work_date if submitted_at is None else assignment.work_date

    try:
        new_visit = Visit(
            assignment_id=assignment.id,
            store_id=assignment.store_id,
            visitor_id=assignment.visitor_id,
            visit_date=visit_date,
            result=normalized_result,
            note=visit_note,
        )
        db.add(new_visit)
        db.flush()

        assignment.assignment_status = AssignmentStatus.COMPLETED.value

        scheduling_service.apply_visit_result_to_schedule(
            db=db,
            store_id=assignment.store_id,
            visit_date=visit_date,
            visit_result=normalized_result,
            commit=False,
        )

        if normalized_result == VisitResult.RED.value:
            telesales_service.create_followup_for_red_visit(
                db=db,
                visit_id=new_visit.id,
                created_by_user_id=None,
                commit=False,
            )

        db.commit()
        return new_visit
    except Exception:
        db.rollback()
        raise


def finalize_unsubmitted_assignments(db: Session, work_date: date, actor_user_id: int) -> int:
    _assert_manager_user(db, actor_user_id)

    pending_assignments = (
        db.query(DailyAssignment)
        .outerjoin(Visit, Visit.assignment_id == DailyAssignment.id)
        .filter(
            DailyAssignment.work_date == work_date,
            DailyAssignment.assignment_status == AssignmentStatus.PUBLISHED.value,
            Visit.id.is_(None),
        )
        .all()
    )

    if not pending_assignments:
        return 0

    created_visits = 0
    try:
        for assignment in pending_assignments:
            auto_visit = Visit(
                assignment_id=assignment.id,
                store_id=assignment.store_id,
                visitor_id=assignment.visitor_id,
                visit_date=assignment.work_date,
                result=VisitResult.RED.value,
                note="Auto-marked red: no visit submitted.",
            )
            db.add(auto_visit)
            db.flush()

            assignment.assignment_status = AssignmentStatus.SKIPPED.value
            created_visits += 1

            scheduling_service.apply_visit_result_to_schedule(
                db=db,
                store_id=assignment.store_id,
                visit_date=assignment.work_date,
                visit_result=VisitResult.RED.value,
                commit=False,
            )
            telesales_service.create_followup_for_red_visit(
                db=db,
                visit_id=auto_visit.id,
                created_by_user_id=actor_user_id,
                commit=False,
            )

        db.commit()
        return created_visits
    except Exception:
        db.rollback()
        raise
