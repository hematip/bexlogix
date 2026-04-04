# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import date, timedelta

from sqlalchemy.orm import Session

from server.app.enums.contact_status import ContactStatus
from server.app.enums.roles import UserRole
from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.enums.visit_result import VisitResult
from server.app.errors import DomainError, PermissionError as AppPermissionError, ValidationError, err
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.repositories import (
    telesales_followup_repository,
    user_repository,
    visit_repository,
)
from server.app.services import scheduling_service
from server.app.services.constants import TELESALES_POSTPONE_DELAY_DAYS
from server.app.utils.calendar import get_next_working_day  # FIX: [BIZ-01] Business-calendar-aware followup dates.


# Contract: _assert_telesales_user executes one deterministic step in the workflow.
def _assert_telesales_user(db: Session, user_id: int) -> None:
    user = user_repository.get_user_by_id(db, user_id)
    if not user:
        raise ValidationError("کاربر فروش تلفنی پیدا نشد.")
    if user.role != UserRole.TELESALES.value:
        raise AppPermissionError(err("telesales_only_submit"))


# Contract: create_followup_for_red_visit executes one deterministic step in the workflow.
def create_followup_for_red_visit(
    db: Session,
    visit_id: int,
    created_by_user_id: int | None,
    commit: bool = True,
) -> TelesalesFollowup:
    visit = visit_repository.get_visit_by_id(db, visit_id)
    if not visit:
        raise ValidationError("ویزیت مرتبط با این پیگیری پیدا نشد.")
    if visit.result != VisitResult.RED.value:
        raise DomainError(err("followup_only_for_red"))

    existing_open = telesales_followup_repository.get_open_followup_by_visit_id(db, visit_id)
    if existing_open:
        return existing_open

    followup = TelesalesFollowup(
        store_id=visit.store_id,
        visit_id=visit.id,
        followup_date=get_next_working_day(visit.visit_date),
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


# Contract: list_pending_followups executes one deterministic step in the workflow.
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


# Contract: submit_followup_result executes one deterministic step in the workflow.
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
        raise ValidationError("وضعیت تماس انتخاب‌شده معتبر نیست.")
    if normalized_result not in allowed_results:
        raise ValidationError("نتیجه پیگیری انتخاب‌شده معتبر نیست.")

    followup = telesales_followup_repository.get_followup_by_id(db, followup_id)
    if not followup:
        raise ValidationError("پیگیری فروش تلفنی پیدا نشد.")
    if followup.result is not None:
        raise DomainError(err("followup_already_finalized"))

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
