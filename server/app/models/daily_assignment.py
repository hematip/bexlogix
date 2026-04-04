# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base

# Daily assignment of a store to a a visitor
# Contract: DailyAssignment defines a typed boundary and should remain behavior-stable.
class DailyAssignment(Base):
    __tablename__ = 'daily_assignments'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # The work date of this assignment
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Assigned visitor
    visitor_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('visitor_profiles.id'),
        nullable=False,
        index=True,
    )

    # Assigned store
    store_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('stores.id'),
        nullable=False,
        index=True,
    )

    # The order of the store inside the generated route
    route_order: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Optional route distance for that stop
    route_distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Current assignment state
    assignment_status: Mapped[str] = mapped_column(String(20), nullable=False, default='draft')

    # The manager user who generated this assignment
    generated_by: Mapped[int | None] = mapped_column(
        ForeignKey('users.id'),
        nullable=True,
        index=True,
    )

    # When this route was published
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

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
