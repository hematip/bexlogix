from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base

# Current scheduling state of each store
class StoreScheduleState(Base):
    __tablename__ = 'store_schedule_states'

    id: Mapped [int] = mapped_column(Integer, primary_key=True, index=True)

    # Each store should have only one current schedule state
    store_id: Mapped [int] = mapped_column(
        ForeignKey('stores.id'),
        unique=True,
        nullable=False,
        index=True,
    )

    # Latest visit information
    last_visit_date: Mapped [date | None] = mapped_column(Date, nullable=True)
    last_visit_result: Mapped [str | None] = mapped_column(String(20), nullable=True)

    # Next planned visit date
    next_visit_date: Mapped [date | None] = mapped_column(Date, nullable=True, index=True)

    # How many days this store is overdue
    overdue_days: Mapped [int] = mapped_column(Integer, default=0, nullable=False)

    # Whether this store is currently waiting for telesales follow-up
    in_telesales_queue: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    update_at: Mapped [datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )