from datetime import date, timedelta

from sqlalchemy.orm import Session

from server.app.enums.contact_status import ContactStatus
from server.app.enums.roles import UserRole
from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.enums.visit_result import VisitResult
from server.app.errors import DomainError, PermissionError as AppPermissionError, ValidationError
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.repositories import (
    telesales_followup_repository,
    user_repository,
    visit_repository,
)
from server.app.services import scheduling_service
from server.app.services.constants import TELESALES_POSTPONE_DELAY_DAYS


def _assert_telesales_user(db: Session, user_id: int) -> None:
    user = user_repository.get_user_by_id(db, user_id)
    if not user:
        raise ValidationError(f"User id {user_id} not found.")
    if user.role != UserRole.TELESALES.value:
        raise AppPermissionError("Only telesales users can submit follow-up results.")


def create_followup_for_red_visit(
    db: Session,
    visit_id: int,
    created_by_user_id: int | None,
    commit: bool = True,
) -> TelesalesFollowup:
    visit = visit_repository.get_visit_by_id(db, visit_id)
    if not visit:
        raise ValidationError(f"Visit id {visit_id} not found.")
    if visit.result != VisitResult.RED.value:
        raise DomainError("Telesales follow-up can only be created for red visits.")

    existing_open = telesales_followup_repository.get_open_followup_by_visit_id(db, visit_id)
    if existing_open:
        return existing_open

    followup = TelesalesFollowup(
        store_id=visit.store_id,
        visit_id=visit.id,
        followup_date=visit.visit_date,
        created_by=created_by_user_id,
    )
    db.add(followup)

    if commit:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

    return followup


def list_pending_followups(db: Session, as_of_date: date | None = None) -> list[dict]:
    rows = telesales_followup_repository.list_pending_followup_rows(db=db, as_of_date=as_of_date)

    pending: list[dict] = []
    for followup, store, visit, visitor in rows:
        pending.append(
            {
                "followup_id": followup.id,
                "followup_date": followup.followup_date.isoformat(),
                "store_id": store.id,
                "store_code": store.store_code,
                "store_name": store.store_name,
                "store_region": store.region,
                "store_address": store.address,
                "store_lat": store.lat,
                "store_lon": store.lon,
                "visit_id": followup.visit_id,
                "visit_date": visit.visit_date.isoformat() if visit else None,
                "visit_result": visit.result if visit else None,
                "visit_note": visit.note if visit else None,
                "visitor_code": visitor.visitor_code if visitor else None,
                "unavailable_reason": (
                    visit.note
                    if visit and visit.note
                    else "ویزیت قرمز ثبت شده (عدم دسترسی/عدم انجام ویزیت)"
                ),
                "note": followup.note,
            }
        )
    return pending


def submit_followup_result(
    db: Session,
    followup_id: int,
    telesales_user_id: int,
    contact_status: str,
    result: str,
    note: str | None,
) -> TelesalesFollowup:
    _assert_telesales_user(db, telesales_user_id)

    normalized_contact_status = str(contact_status or "").strip().lower()
    normalized_result = str(result or "").strip().lower()

    allowed_contact_statuses = {item.value for item in ContactStatus}
    allowed_results = {item.value for item in TelesalesOutcome}

    if normalized_contact_status not in allowed_contact_statuses:
        raise ValidationError(f"Invalid contact_status: {contact_status}")
    if normalized_result not in allowed_results:
        raise ValidationError(f"Invalid telesales result: {result}")

    followup = telesales_followup_repository.get_followup_by_id(db, followup_id)
    if not followup:
        raise ValidationError(f"Telesales followup id {followup_id} not found.")
    if followup.result is not None:
        raise DomainError("This follow-up is already finalized.")

    try:
        followup.contact_status = normalized_contact_status
        followup.result = normalized_result
        followup.note = str(note or "").strip() or None
        scheduling_service.apply_telesales_outcome_to_schedule(
            db=db,
            store_id=followup.store_id,
            followup_date=followup.followup_date,
            outcome=normalized_result,
            commit=False,
        )

        if normalized_result == TelesalesOutcome.POSTPONE.value:
            next_followup = TelesalesFollowup(
                store_id=followup.store_id,
                visit_id=followup.visit_id,
                followup_date=followup.followup_date + timedelta(days=TELESALES_POSTPONE_DELAY_DAYS),
                created_by=telesales_user_id,
            )
            db.add(next_followup)

        db.commit()
        return followup
    except Exception:
        db.rollback()
        raise
