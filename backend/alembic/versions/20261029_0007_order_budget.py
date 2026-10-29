"""Explicit confirmed budget; historical budgets and request identities stay unknown."""
from alembic import op
import sqlalchemy as sa

revision = "20261029_0007"
down_revision = "20261011_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("purchase_orders", sa.Column("total_budget", sa.Numeric(14, 2), nullable=True))
    op.add_column("purchase_orders", sa.Column("request_fingerprint", sa.String(64), nullable=True))
    op.add_column("purchase_orders", sa.Column("requested_items_json", sa.Text(), nullable=True))
    op.add_column("agent_runs", sa.Column("total_budget", sa.Numeric(14, 2), nullable=True))


def downgrade():
    op.drop_column("agent_runs", "total_budget")
    for name in ("requested_items_json", "request_fingerprint", "total_budget"):
        op.drop_column("purchase_orders", name)
