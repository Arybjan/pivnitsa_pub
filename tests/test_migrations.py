import os
import subprocess
import sys

from app.core.config import Settings


def test_jwt_environment_alias(monkeypatch):
    monkeypatch.delenv("JWT_SECRET")
    monkeypatch.setenv("JWT_SECRET_KEY", "compose-secret")
    assert Settings(_env_file=None).jwt_secret == "compose-secret"
    monkeypatch.setenv("JWT_SECRET", "canonical-secret")
    assert Settings(_env_file=None).jwt_secret == "canonical-secret"


def test_migrations_from_empty_database(tmp_path):
    environment = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'events.db'}"}
    for _ in range(2):
        result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=environment, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    import sqlite3
    with sqlite3.connect(tmp_path / "events.db") as db:
        assert db.execute("select version_num from alembic_version").fetchone() == ("0003",)
        tables = {row[0] for row in db.execute("select name from sqlite_master where type='table'")}
        assert {"events", "event_outbox"} <= tables


import pytest


@pytest.mark.asyncio
async def test_postgres_legacy_authors_keep_integer_ids():
    import asyncpg
    from uuid import uuid4
    from datetime import timezone
    url = os.environ.get("EVENT_TEST_DATABASE_URL")
    if not url or not url.startswith("postgresql"):
        pytest.skip("Requires isolated PostgreSQL instance with CREATE DATABASE")
    admin = await asyncpg.connect(url.replace("postgresql+asyncpg", "postgresql"))
    database_name = "event_migration_" + uuid4().hex
    await admin.execute(f'CREATE DATABASE "{database_name}"')
    database_url = url.rsplit("/", 1)[0] + "/" + database_name
    environment = {**os.environ, "DATABASE_URL": database_url}
    connection = None
    try:
        def migrate(target):
            return subprocess.run([sys.executable, "-m", "alembic", "upgrade", target], env=environment, capture_output=True, text=True)
        first = migrate("0001")
        assert first.returncode == 0, first.stderr
        connection = await asyncpg.connect(database_url.replace("postgresql+asyncpg", "postgresql"))
        await connection.execute("DROP TABLE alembic_version")
        await connection.execute("""
            INSERT INTO events (title, start_datetime, status, created_by)
            VALUES ('Legacy', '2030-08-20 18:00:00', 'ARCHIVED', 123)
        """)
        failed = migrate("head")
        assert failed.returncode != 0
        assert "event_author_map" in failed.stderr
        assert await connection.fetchval("SELECT created_by FROM events") == 123
        await connection.execute("CREATE TABLE event_author_map (legacy_id bigint PRIMARY KEY, user_id uuid NOT NULL)")
        await connection.execute("INSERT INTO event_author_map VALUES (123, '6be6b360-313a-4f67-bafd-9dd1bdbd7c31')")
        upgraded = migrate("head")
        assert upgraded.returncode == 0, upgraded.stderr
        row = await connection.fetchrow("SELECT created_by, start_datetime, status FROM events")
        assert row["created_by"] == 123
        assert row["status"] == "FINISHED"
        assert row["start_datetime"].astimezone(timezone.utc).hour == 18
        repeated = migrate("head")
        assert repeated.returncode == 0, repeated.stderr
    finally:
        if connection:
            await connection.close()
        await admin.execute(f'DROP DATABASE "{database_name}"')
        await admin.close()
