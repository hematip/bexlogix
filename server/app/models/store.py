# Purpose: Python module in BexLogix project.
# Workflow Role: Supports operational planning and execution flow.

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base

# Store master data
# Contract: Store defines a typed boundary and should remain behavior-stable.
class Store(Base):
    __tablename__ = 'stores'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    store_name: Mapped[str] = mapped_column(String(150), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)

    grade: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    has_confectionery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_oil: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_pasta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

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
