"""agent runs and tool traces

Revision ID: 20261010_0004
Revises: 20261010_0003
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261010_0004"
down_revision: str | None = "20261010_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("purchase_order_id", sa.Integer(), nullable=True),
        sa.Column("state_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["purchase_order_id"], ["purchase_orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agent_runs_status"), "agent_runs", ["status"], unique=False)

    op.create_table(
        "tool_traces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_index", sa.Integer(), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_traces_run_id"), "tool_traces", ["run_id"], unique=False)
    op.create_index(op.f("ix_tool_traces_status"), "tool_traces", ["status"], unique=False)
    op.create_index(op.f("ix_tool_traces_tool_name"), "tool_traces", ["tool_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tool_traces_tool_name"), table_name="tool_traces")
    op.drop_index(op.f("ix_tool_traces_status"), table_name="tool_traces")
    op.drop_index(op.f("ix_tool_traces_run_id"), table_name="tool_traces")
    op.drop_table("tool_traces")
    op.drop_index(op.f("ix_agent_runs_status"), table_name="agent_runs")
    op.drop_table("agent_runs")
