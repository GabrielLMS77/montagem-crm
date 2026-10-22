from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from clinicaflow.core.base import Base


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_sales_amount_positive"),
        CheckConstraint("status IN ('pending', 'paid', 'cancelled')", name="ck_sales_status"),
        Index("ix_sales_sale_date", "sale_date"),
        Index("ix_sales_customer_id", "customer_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sale_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(
        String(10), default="pending", server_default="pending", nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
