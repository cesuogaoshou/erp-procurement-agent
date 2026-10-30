"""Material aliases for bounded semantic resolution."""
from alembic import op
import sqlalchemy as sa

revision = "20261030_0008"
down_revision = "20261029_0007"
branch_labels = None
depends_on = None


SEED_ALIASES = {
    "MAT-001": ("轴承", "标准件", "轴承件", "bearings"),
    "MAT-002": ("铝壳", "外壳", "铝合金件", "aluminum shell"),
    "MAT-003": ("传感器", "感应器", "sensor"),
    "MAT-004": ("伺服", "电机", "马达", "servo motor"),
    "MAT-005": ("面板", "控制屏", "control panel"),
    "MAT-006": ("密封圈", "O型圈", "胶圈", "seal ring"),
    "MAT-007": ("电源", "模块电源", "power module"),
    "MAT-008": ("导轨", "滑轨", "guide rail"),
    "MAT-009": ("托盘", "包装盘", "pallet"),
    "MAT-010": ("紧固件", "螺丝包", "五金包", "fastener kit"),
}


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("material_aliases"):
        op.create_table(
            "material_aliases",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("material_id", sa.Integer(), nullable=False),
            sa.Column("alias", sa.String(length=120), nullable=False),
            sa.Column("locale", sa.String(length=20), nullable=False, server_default="zh-CN"),
            sa.Column("source", sa.String(length=32), nullable=False, server_default="seed"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.ForeignKeyConstraint(["material_id"], ["materials.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("material_id", "alias", name="uq_material_alias"),
        )
        op.create_index("ix_material_aliases_material_id", "material_aliases", ["material_id"])
        op.create_index("ix_material_aliases_alias", "material_aliases", ["alias"])

    # Existing SQLite demo databases may already have the table because the
    # application creates schema directly. Populate aliases for existing rows
    # without touching any business data.
    materials = sa.table("materials", sa.column("id", sa.Integer), sa.column("code", sa.String))
    aliases = sa.table(
        "material_aliases",
        sa.column("material_id", sa.Integer),
        sa.column("alias", sa.String),
        sa.column("locale", sa.String),
        sa.column("source", sa.String),
        sa.column("active", sa.Boolean),
    )
    for code, values in SEED_ALIASES.items():
        material_id = bind.execute(sa.select(materials.c.id).where(materials.c.code == code)).scalar()
        if material_id is None:
            continue
        for alias in values:
            exists = bind.execute(
                sa.select(sa.func.count())
                .select_from(aliases)
                .where(aliases.c.material_id == material_id, aliases.c.alias == alias)
            ).scalar()
            if not exists:
                bind.execute(
                    aliases.insert().values(
                        material_id=material_id,
                        alias=alias,
                        locale="zh-CN",
                        source="seed",
                        active=True,
                    )
                )


def downgrade():
    op.drop_index("ix_material_aliases_alias", table_name="material_aliases")
    op.drop_index("ix_material_aliases_material_id", table_name="material_aliases")
    op.drop_table("material_aliases")
