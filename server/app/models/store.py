from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from server.db.base import Base

# Store master data.
class Store(Base):
    __tablename__ = 'store'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    store_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    store_name: Mapped[str] = mapped_column(String(150), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=False)

    grade: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    has_confectionery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_oil: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    has_pasta: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
