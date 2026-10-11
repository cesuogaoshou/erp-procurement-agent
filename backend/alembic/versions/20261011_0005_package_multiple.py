"""supplier material package multiples

Revision ID: 20261011_0005
Revises: 20261010_0004
Create Date: 2026-10-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261011_0005"
down_revision: str | None = "20261010_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "supplier_materials",
        sa.Column(
            "package_multiple",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="1",
        ),
    )
    op.alter_column("supplier_materials", "package_multiple", server_default=None)


def downgrade() -> None:
    op.drop_column("supplier_materials", "package_multiple")
