"""add staff authentication and appointment agenda

Revision ID: d19b5a7c4e21
Revises: c514f6dd3ccf
Create Date: 2026-10-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d19b5a7c4e21"
down_revision: Union[str, Sequence[str], None] = "2f3c8a7b1d40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="employee"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "login_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash", name="uq_login_sessions_token_hash"),
    )
    op.create_index("ix_login_sessions_token_hash", "login_sessions", ["token_hash"], unique=True)
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])
    op.create_table(
        "appointment_intakes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("service", sa.String(200), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('pending', 'scheduled')", name="ck_appointment_intakes_status"),
    )
    op.create_index("ix_intakes_employee_requested", "appointment_intakes", ["employee_id", "requested_at", "status"])
    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("intake_id", sa.Integer(), nullable=True),
        sa.Column("service", sa.String(200), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["employee_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["intake_id"], ["appointment_intakes.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("intake_id", name="uq_appointments_intake_id"),
        sa.CheckConstraint("status IN ('scheduled', 'completed', 'no_show', 'cancelled')", name="ck_appointments_status"),
    )
    op.create_index("ix_appointments_employee_starts", "appointments", ["employee_id", "starts_at"])
    op.create_index("ix_appointments_starts", "appointments", ["starts_at"])


def downgrade() -> None:
    op.drop_index("ix_appointments_starts", table_name="appointments")
    op.drop_index("ix_appointments_employee_starts", table_name="appointments")
    op.drop_table("appointments")
    op.drop_index("ix_intakes_employee_requested", table_name="appointment_intakes")
    op.drop_table("appointment_intakes")
    op.drop_index("ix_login_sessions_user_id", table_name="login_sessions")
    op.drop_index("ix_login_sessions_token_hash", table_name="login_sessions")
    op.drop_table("login_sessions")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
