from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base

# Profile data for user with visitor role
class VisitorProfile(Base):
    __tablename__ = 'visitor_profiles'

    # Link each visitor profile to exactly one user account
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey('users.id'),
        unique=True,
        nullable=False,
        index=True,
    )

    # Business-facing visitor code, not internal database id
    visitor_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)

    full_name: Mapped[str] = mapped_column(String(150), nullable=False)

    # Default start location for route generation
    default_start_lat: Mapped[float] = mapped_column(Float, nullable=True)
    default_start_lon: Mapped[float] = mapped_column(Float, nullable=True)

    # Default daily capacity for this visitor
    default_capacity: Mapped[int] = mapped_column(Integer, default=30, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

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




