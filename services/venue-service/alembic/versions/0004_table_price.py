import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # Существующие столы остаются без цены (NULL), данные не меняются
    with op.batch_alter_table("venue_tables") as batch:
        batch.add_column(sa.Column("price", sa.Numeric(12, 2)))
        batch.create_check_constraint("ck_table_price", "price IS NULL OR price >= 0")


def downgrade():
    with op.batch_alter_table("venue_tables") as batch:
        batch.drop_constraint("ck_table_price", type_="check")
        batch.drop_column("price")
