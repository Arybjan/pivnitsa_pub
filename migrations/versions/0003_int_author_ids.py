"""Use Auth integer user IDs for event authors.

Auth Service issues numeric user IDs (JWT "sub" = "1", "2", ...), so UUID authors
from revision 0002 are converted back to bigint. For populated databases the
event_author_map(legacy_id bigint, user_id uuid) table from 0002 is used in reverse.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        populated = connection.execute(sa.text("SELECT EXISTS(SELECT 1 FROM events)")).scalar()
        if populated:
            if not sa.inspect(connection).has_table("event_author_map"):
                raise RuntimeError("Provide event_author_map(legacy_id bigint, user_id uuid) to migrate existing authors")
            missing = connection.execute(sa.text(
                "SELECT count(*) FROM events e LEFT JOIN event_author_map m ON m.user_id=e.created_by WHERE m.legacy_id IS NULL"
            )).scalar()
            if missing:
                raise RuntimeError("event_author_map is missing integer IDs for existing authors")
            op.add_column("events", sa.Column("author_id", sa.BigInteger))
            connection.execute(sa.text("UPDATE events e SET author_id=m.legacy_id FROM event_author_map m WHERE e.created_by=m.user_id"))
            op.drop_index("idx_events_created_by", table_name="events")
            op.drop_column("events", "created_by")
            op.alter_column("events", "author_id", new_column_name="created_by", nullable=False)
            op.create_index("idx_events_created_by", "events", ["created_by"])
        else:
            op.alter_column("events", "created_by", type_=sa.BigInteger, postgresql_using="NULL::bigint")
    else:
        if connection.execute(sa.text("SELECT count(*) FROM events")).scalar():
            raise RuntimeError("Author ID migration is supported on PostgreSQL only")
        with op.batch_alter_table("events") as batch:
            batch.alter_column("created_by", type_=sa.BigInteger, existing_type=sa.Uuid)


def downgrade():
    raise RuntimeError("Integer author IDs cannot be safely converted back to UUIDs")
