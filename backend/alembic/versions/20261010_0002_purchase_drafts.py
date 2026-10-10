"""purchase drafts

Revision ID: 20261010_0002
Revises: 20261010_0001
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0002"
down_revision: str | None = "20261010_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("evidence_refs_json", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_purchase_orders_idempotency_key"), "purchase_orders", ["idempotency_key"], unique=False)
    op.create_index(op.f("ix_purchase_orders_status"), "purchase_orders", ["status"], unique=False)
    op.create_index(op.f("ix_purchase_orders_supplier_id"), "purchase_orders", ["supplier_id"], unique=False)

    op.create_table(
        "purchase_order_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_amount", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["order_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_purchase_order_items_material_id"), "purchase_order_items", ["material_id"], unique=False)
    op.create_index(op.f("ix_purchase_order_items_order_id"), "purchase_order_items", ["order_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_purchase_order_items_order_id"), table_name="purchase_order_items")
    op.drop_index(op.f("ix_purchase_order_items_material_id"), table_name="purchase_order_items")
    op.drop_table("purchase_order_items")
    op.drop_index(op.f("ix_purchase_orders_supplier_id"), table_name="purchase_orders")
    op.drop_index(op.f("ix_purchase_orders_status"), table_name="purchase_orders")
    op.drop_index(op.f("ix_purchase_orders_idempotency_key"), table_name="purchase_orders")
    op.drop_table("purchase_orders")
