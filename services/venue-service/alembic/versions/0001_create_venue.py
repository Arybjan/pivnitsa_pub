import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "halls",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("map_image_url", sa.String(2048)),
        sa.Column("map_width", sa.Integer(), nullable=False),
        sa.Column("map_height", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_hall_name"),
        sa.CheckConstraint(
            "map_width > 0 AND map_height > 0", name="ck_hall_dimensions"
        ),
    )
    op.create_index(
        "uq_hall_active_name",
        "halls",
        ["name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "venue_tables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "hall_id",
            sa.Integer(),
            sa.ForeignKey("halls.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("x", sa.Float(), nullable=False),
        sa.Column("y", sa.Float(), nullable=False),
        sa.Column("rotation", sa.Float(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        *timestamps(),
        sa.CheckConstraint("number > 0", name="ck_table_number"),
        sa.CheckConstraint("capacity > 0", name="ck_table_capacity"),
        sa.CheckConstraint(
            "x >= 0 AND x <= 1 AND y >= 0 AND y <= 1", name="ck_table_position"
        ),
        sa.CheckConstraint(
            "rotation >= 0 AND rotation < 360", name="ck_table_rotation"
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'UNAVAILABLE')", name="ck_table_status"
        ),
    )
    op.create_index("ix_venue_tables_hall_id", "venue_tables", ["hall_id"])
    op.create_index(
        "uq_table_active_number",
        "venue_tables",
        ["hall_id", "number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_table(
        "table_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "table_id",
            sa.Integer(),
            sa.ForeignKey("venue_tables.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        *timestamps(),
        sa.CheckConstraint("ends_at > starts_at", name="ck_block_period"),
    )
    op.create_index(
        "ix_block_table_period", "table_blocks", ["table_id", "starts_at", "ends_at"]
    )


def downgrade():
    op.drop_table("table_blocks")
    op.drop_table("venue_tables")
    op.drop_table("halls")
