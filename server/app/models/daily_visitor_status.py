# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base

# Daily operational status for each visitor
# Contract: DailyVisitorStatus defines a typed boundary and should remain behavior-stable.
class DailyVisitorStatus(Base):
    __tablename__ = 'daily_visitor_statuses'

    __table_args__ = (
        UniqueConstraint("visitor_id", "work_date", name="uq_daily_visitor_status_visitor_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Link this daily status to one visitor profile
    visitor_id: Mapped[int] = mapped_column(
        ForeignKey('visitor_profiles.id'),
        nullable=False,
        index=True,
    )

    # The working date for this status row
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Actual start point for that day
    start_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Actual daily visit capacity for that day
    capacity: Mapped[int] = mapped_column(Integer, default=30, nullable=False)

    # Whether the visitor is active on that specific day
    is_active_today: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
