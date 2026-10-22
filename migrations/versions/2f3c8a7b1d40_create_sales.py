"""create sales

Revision ID: 2f3c8a7b1d40
Revises: c514f6dd3ccf
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2f3c8a7b1d40"
down_revision: Union[str, Sequence[str], None] = "c514f6dd3ccf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("sale_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=10), server_default="pending", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_sales_amount_positive"),
        sa.CheckConstraint("status IN ('pending', 'paid', 'cancelled')", name="ck_sales_status"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sales_sale_date", "sales", ["sale_date"])
    op.create_index("ix_sales_customer_id", "sales", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_sales_customer_id", table_name="sales")
    op.drop_index("ix_sales_sale_date", table_name="sales")
    op.drop_table("sales")
