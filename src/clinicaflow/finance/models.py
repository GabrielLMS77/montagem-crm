from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from clinicaflow.core.base import Base


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_financial_transactions_amount_positive",
        ),
        CheckConstraint(
            "transaction_type IN ('income', 'expense')",
            name="ck_financial_transactions_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'paid', 'cancelled')",
            name="ck_financial_transactions_status",
        ),
        Index("ix_financial_transactions_due_date", "due_date"),
        Index("ix_financial_transactions_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    description: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    transaction_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(10),
        default="pending",
        server_default="pending",
        nullable=False,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
    )

    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=True,
    )

    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id", ondelete="RESTRICT"),
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )