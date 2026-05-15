# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from server.app.errors import DomainError, PermissionError as AppPermissionError, ValidationError, err
from server.app.enums.assignment_status import AssignmentStatus
from server.app.enums.roles import UserRole
from server.app.enums.visit_result import VisitResult
from server.app.models.visit import Visit
from server.app.repositories import (
    assignment_repository,
    user_repository,
    visit_repository,
    visitor_repository,
)
from server.app.services import scheduling_service, telesales_service


# Contract: _assert_manager_user executes one deterministic step in the workflow.
def _assert_manager_user(db: Session, user_id: int) -> None:
    user = user_repository.get_user_by_id(db, user_id)
    if not user:
        raise ValidationError(err("manager_user_not_found"))
    if user.role != UserRole.MANAGER.value:
        raise AppPermissionError(err("manager_only_finalize"))


# Contract: submit_visit_result executes one deterministic step in the workflow.
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
        raise ValidationError(err("invalid_visit_result"))

    assignment = assignment_repository.get_assignment_by_id(db, assignment_id)
    if not assignment:
        raise ValidationError(err("assignment_not_found"))
    if assignment.assignment_status != AssignmentStatus.PUBLISHED.value:
        raise DomainError(err("visit_only_published"))

    visitor_profile = visitor_repository.get_profile_by_id(db, assignment.visitor_id)
    if not visitor_profile:
        raise ValidationError(err("visitor_profile_not_found"))
    if visitor_profile.user_id != visitor_user_id:
        raise AppPermissionError(err("visit_only_own_assignment"))

    existing_visit = visit_repository.get_visit_by_assignment_id(db, assignment.id)
    if existing_visit:
        raise DomainError(err("visit_already_submitted"))

    visit_note = str(note or "").strip() or None
    visit_date = assignment.work_date if submitted_at is None else submitted_at.date()

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
        try:
            db.flush()
        except IntegrityError as exc:
            # FIX: [CONCURRENCY] uq_visit_assignment_id stops duplicates even
            # when two requests slip past the read check above.
            db.rollback()
            raise DomainError(err("visit_already_submitted")) from exc

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
    except DomainError:
        raise
    except Exception:
        db.rollback()
        raise


# Contract: finalize_unsubmitted_assignments executes one deterministic step in the workflow.
def finalize_unsubmitted_assignments(db: Session, work_date: date, actor_user_id: int) -> int:
    _assert_manager_user(db, actor_user_id)

    pending_assignments = visit_repository.list_pending_published_assignments_without_visit(
        db=db,
        work_date=work_date,
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
