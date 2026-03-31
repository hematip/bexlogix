from datetime import date, timedelta

from sqlalchemy.orm import Session

from server.app.enums.contact_status import ContactStatus
from server.app.enums.roles import UserRole
from server.app.enums.telesales_outcome import TelesalesOutcome
from server.app.enums.visit_result import VisitResult
from server.app.models.store import Store
from server.app.models.telesales_followup import TelesalesFollowup
from server.app.models.user import User
from server.app.models.visit import Visit
from server.app.services import scheduling_service
from server.app.services.constants import TELESALES_POSTPONE_DELAY_DAYS


def _assert_telesales_user(db: Session, user_id: int) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User id {user_id} not found.")
    if user.role != UserRole.TELESALES.value:
        raise ValueError("Only telesales users can submit follow-up results.")


def create_followup_for_red_visit(
    db: Session,
    visit_id: int,
    created_by_user_id: int | None,
    commit: bool = True,
) -> TelesalesFollowup:
    visit = db.query(Visit).filter(Visit.id == visit_id).first()
    if not visit:
        raise ValueError(f"Visit id {visit_id} not found.")
    if visit.result != VisitResult.RED.value:
        raise ValueError("Telesales follow-up can only be created for red visits.")

    existing_open = (
        db.query(TelesalesFollowup)
        .filter(
            TelesalesFollowup.visit_id == visit_id,
            TelesalesFollowup.result.is_(None),
        )
        .first()
    )
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
    query = (
        db.query(TelesalesFollowup, Store)
        .join(Store, Store.id == TelesalesFollowup.store_id)
        .filter(TelesalesFollowup.result.is_(None))
    )
    if as_of_date is not None:
        query = query.filter(TelesalesFollowup.followup_date <= as_of_date)

    rows = query.order_by(TelesalesFollowup.followup_date, Store.store_code).all()
    pending = []
    for followup, store in rows:
        pending.append(
            {
                "followup_id": followup.id,
                "followup_date": followup.followup_date.isoformat(),
                "store_id": store.id,
                "store_code": store.store_code,
                "store_name": store.store_name,
                "visit_id": followup.visit_id,
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
        raise ValueError(f"Invalid contact_status: {contact_status}")
    if normalized_result not in allowed_results:
        raise ValueError(f"Invalid telesales result: {result}")

    followup = db.query(TelesalesFollowup).filter(TelesalesFollowup.id == followup_id).first()
    if not followup:
        raise ValueError(f"Telesales followup id {followup_id} not found.")
    if followup.result is not None:
        raise ValueError("This follow-up is already finalized.")

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
