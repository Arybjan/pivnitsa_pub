"""Create the original events schema; adopt pre-existing legacy tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if sa.inspect(op.get_bind()).has_table("events"):
        return
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("poster_url", sa.String(500)),
        sa.Column("start_datetime", sa.DateTime, nullable=False),
        sa.Column("end_datetime", sa.DateTime),
        sa.Column("status", sa.Enum("DRAFT", "PUBLISHED", "CANCELLED", "ARCHIVED", name="eventstatus"), nullable=False),
        sa.Column("created_by", sa.BigInteger, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    for name, columns in (
        ("ix_events_id", ["id"]), ("idx_events_status", ["status"]),
        ("idx_events_start_datetime", ["start_datetime"]),
        ("idx_events_created_by", ["created_by"]),
        ("idx_events_status_start", ["status", "start_datetime"]),
    ):
        op.create_index(name, "events", columns)


def downgrade():
    op.drop_table("events")
    if op.get_bind().dialect.name == "postgresql":
        sa.Enum(name="eventstatus").drop(op.get_bind(), checkfirst=True)
