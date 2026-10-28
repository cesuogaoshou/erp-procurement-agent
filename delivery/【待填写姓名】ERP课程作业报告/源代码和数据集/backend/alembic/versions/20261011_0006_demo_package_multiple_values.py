"""demo package multiple values

Revision ID: 20261011_0006
Revises: 20261011_0005
Create Date: 2026-10-11
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261011_0006"
down_revision: str | None = "20261011_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE supplier_materials "
        "SET package_multiple = 10 "
        "WHERE material_id IN (9, 10)"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE supplier_materials "
        "SET package_multiple = 1 "
        "WHERE material_id IN (9, 10)"
    )
