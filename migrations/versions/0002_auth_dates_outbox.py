"""Use Auth UUIDs, UTC timestamps, FINISHED status and transactional outbox.

Legacy integer author IDs cannot be mapped to Auth UUIDs automatically.
For populated databases, supply an event_author_map(legacy_id bigint, user_id uuid)
with an entry for each author before applying this revision.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
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
                "SELECT count(*) FROM events e LEFT JOIN event_author_map m ON m.legacy_id=e.created_by WHERE m.user_id IS NULL"
            )).scalar()
            if missing:
                raise RuntimeError("event_author_map is missing UUIDs for existing authors")
            op.add_column("events", sa.Column("author_uuid", sa.Uuid))
            connection.execute(sa.text("UPDATE events e SET author_uuid=m.user_id FROM event_author_map m WHERE e.created_by=m.legacy_id"))
            op.drop_index("idx_events_created_by", table_name="events")
            op.drop_column("events", "created_by")
            op.alter_column("events", "author_uuid", new_column_name="created_by", nullable=False)
            op.create_index("idx_events_created_by", "events", ["created_by"])
        else:
            op.alter_column("events", "created_by", type_=sa.Uuid, postgresql_using="NULL::uuid")
        for column in ("start_datetime", "end_datetime", "created_at", "updated_at"):
            op.alter_column("events", column, type_=sa.DateTime(timezone=True), postgresql_using=f"{column} AT TIME ZONE 'UTC'")
        connection.execute(sa.text("ALTER TYPE eventstatus RENAME VALUE 'ARCHIVED' TO 'FINISHED'"))
    else:
        if connection.execute(sa.text("SELECT count(*) FROM events")).scalar():
            raise RuntimeError("Legacy author migration is supported on PostgreSQL only")
        with op.batch_alter_table("events") as batch:
            batch.alter_column("created_by", type_=sa.Uuid, existing_type=sa.BigInteger)
            batch.alter_column("status", type_=sa.Enum("DRAFT", "PUBLISHED", "CANCELLED", "FINISHED", name="eventstatus"), existing_type=sa.String(9))
            for column in ("start_datetime", "end_datetime", "created_at", "updated_at"):
                batch.alter_column(column, type_=sa.DateTime(timezone=True), existing_type=sa.DateTime)
    op.create_table(
        "event_outbox",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("routing_key", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    raise RuntimeError("UUID author IDs cannot be safely converted back to legacy integer IDs")
