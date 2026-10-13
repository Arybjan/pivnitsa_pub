import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # batch - чтобы CHECK добавлялся и в SQLite (тесты)
    with op.batch_alter_table("venue_tables") as batch:
        batch.add_column(sa.Column("width", sa.Float()))
        batch.add_column(sa.Column("height", sa.Float()))
        batch.create_check_constraint(
            "ck_table_size",
            "(width IS NULL OR (width > 0 AND width <= 1))"
            " AND (height IS NULL OR (height > 0 AND height <= 1))",
        )


def downgrade():
    with op.batch_alter_table("venue_tables") as batch:
        batch.drop_constraint("ck_table_size", type_="check")
        batch.drop_column("height")
        batch.drop_column("width")
