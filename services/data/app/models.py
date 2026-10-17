from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, Numeric, Uuid, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OrderRecord(Base):
    __tablename__ = "order_records"
    __table_args__ = (
        CheckConstraint("quantity BETWEEN 1 AND 1000000", name="ck_order_records_quantity_range"),
        CheckConstraint("total > 0", name="ck_order_records_total_positive"),
        Index("ix_order_records_recorded_at", "recorded_at"),
        {"schema": "data"},
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    order_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, unique=True)
    product_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
