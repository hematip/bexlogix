# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base

# Actual visit result for an assigned store
# Contract: Visit defines a typed boundary and should remain behavior-stable.
class Visit(Base):
    __tablename__ = 'visits'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Link this visit to the daily assignment
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey('daily_assignments.id'),
        nullable=False,
        index=True,
    )

    # Redundant references kept for easier querying and reporting
    store_id: Mapped[int] = mapped_column(
        ForeignKey('stores.id'),
        nullable=False,
        index=True,
    )

    visitor_id: Mapped[int] = mapped_column(
        ForeignKey('visitor_profiles.id'),
        nullable=False,
        index=True,
    )

    # The actual date of the visit
    visit_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # green / yellow / red
    result: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Optional note written by the visitor
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

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
