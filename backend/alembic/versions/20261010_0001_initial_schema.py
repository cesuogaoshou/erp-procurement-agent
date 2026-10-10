"""initial schema

Revision ID: 20261010_0001
Revises:
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=False),
        sa.Column("safety_stock", sa.Numeric(12, 2), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_materials_code"), "materials", ["code"], unique=False)

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "demand_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("demand_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_demand_history_demand_date"), "demand_history", ["demand_date"], unique=False)
    op.create_index(op.f("ix_demand_history_material_id"), "demand_history", ["material_id"], unique=False)

    op.create_table(
        "inventory",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("on_hand", sa.Numeric(12, 2), nullable=False),
        sa.Column("reserved", sa.Numeric(12, 2), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("material_id"),
    )

    op.create_table(
        "supplier_materials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("lead_time_days", sa.Integer(), nullable=False),
        sa.Column("moq", sa.Numeric(12, 2), nullable=False),
        sa.Column("capacity", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supplier_materials_material_id"), "supplier_materials", ["material_id"], unique=False)
    op.create_index(op.f("ix_supplier_materials_supplier_id"), "supplier_materials", ["supplier_id"], unique=False)

    op.create_table(
        "supplier_performance",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier_id", sa.Integer(), nullable=False),
        sa.Column("material_id", sa.Integer(), nullable=False),
        sa.Column("observed_until", sa.Date(), nullable=False),
        sa.Column("avg_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("promised_deliveries", sa.Integer(), nullable=False),
        sa.Column("on_time_deliveries", sa.Integer(), nullable=False),
        sa.Column("inspected_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("accepted_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("complaint_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
        sa.ForeignKeyConstraint(["supplier_id"], ["suppliers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_supplier_performance_material_id"), "supplier_performance", ["material_id"], unique=False)
    op.create_index(op.f("ix_supplier_performance_supplier_id"), "supplier_performance", ["supplier_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_supplier_performance_supplier_id"), table_name="supplier_performance")
    op.drop_index(op.f("ix_supplier_performance_material_id"), table_name="supplier_performance")
    op.drop_table("supplier_performance")
    op.drop_index(op.f("ix_supplier_materials_supplier_id"), table_name="supplier_materials")
    op.drop_index(op.f("ix_supplier_materials_material_id"), table_name="supplier_materials")
    op.drop_table("supplier_materials")
    op.drop_table("inventory")
    op.drop_index(op.f("ix_demand_history_material_id"), table_name="demand_history")
    op.drop_index(op.f("ix_demand_history_demand_date"), table_name="demand_history")
    op.drop_table("demand_history")
    op.drop_table("suppliers")
    op.drop_index(op.f("ix_materials_code"), table_name="materials")
    op.drop_table("materials")
