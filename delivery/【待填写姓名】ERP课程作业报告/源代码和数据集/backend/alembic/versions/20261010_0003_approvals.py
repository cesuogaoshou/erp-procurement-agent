"""approvals

Revision ID: 20261010_0003
Revises: 20261010_0002
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0003"
down_revision: str | None = "20261010_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("purchase_orders", sa.Column("formal_order_number", sa.String(length=32), nullable=True))
    op.add_column("purchase_orders", sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_index(
        "ux_purchase_orders_formal_order_number",
        "purchase_orders",
        ["formal_order_number"],
        unique=True,
    )

    op.create_table(
        "approval_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=80), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("order_version_before", sa.Integer(), nullable=False),
        sa.Column("order_version_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_approval_records_actor_user_id"), "approval_records", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_approval_records_decision"), "approval_records", ["decision"], unique=False)
    op.create_index(op.f("ix_approval_records_idempotency_key"), "approval_records", ["idempotency_key"], unique=False)
    op.create_index(op.f("ix_approval_records_order_id"), "approval_records", ["order_id"], unique=False)

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.String(length=80), nullable=False),
        sa.Column("actor_role", sa.String(length=32), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_audit_logs_order_id"), "audit_logs", ["order_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_order_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index(op.f("ix_approval_records_order_id"), table_name="approval_records")
    op.drop_index(op.f("ix_approval_records_idempotency_key"), table_name="approval_records")
    op.drop_index(op.f("ix_approval_records_decision"), table_name="approval_records")
    op.drop_index(op.f("ix_approval_records_actor_user_id"), table_name="approval_records")
    op.drop_table("approval_records")
    op.drop_index("ux_purchase_orders_formal_order_number", table_name="purchase_orders")
    op.drop_column("purchase_orders", "updated_at")
    op.drop_column("purchase_orders", "formal_order_number")
