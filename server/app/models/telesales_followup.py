# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base

# Follow-up record created for red visits
# Contract: TelesalesFollowup defines a typed boundary and should remain behavior-stable.
class TelesalesFollowup(Base):
    __tablename__ = 'telesales_followups'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Store related to this telesales follow-up
    store_id: Mapped[int] = mapped_column(
        ForeignKey('stores.id'),
        nullable=False,
        index=True,
    )

    # The red visit that triggered this telesales task
    visit_id: Mapped[int] = mapped_column(
        ForeignKey('visits.id'),
        nullable=False,
        index=True,
    )

    # The date of telesales follow-up
    followup_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # reached / not_reached
    contact_status: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # sale_done / no_need / postpone / invalid
    result: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)

    # Optional note from telesales operator
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User who registered this follow-up
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey('users.id'),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
