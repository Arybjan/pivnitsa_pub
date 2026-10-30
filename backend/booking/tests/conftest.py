"""Тесты на PostgreSQL (миграции booking используют ALTER TYPE и частичные индексы).

    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5440/booking_test pytest
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if not TEST_DATABASE_URL:
    pytest.skip("TEST_DATABASE_URL is not set", allow_module_level=True)

os.environ.update(
    DATABASE_URL=TEST_DATABASE_URL,
    JWT_SECRET="booking-test-secret-that-is-long-enough",
    VENUE_TIMEZONE="Asia/Bishkek",
)

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.main import app  # noqa: E402
from app.messaging.publisher import publisher  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def database():
    admin = create_engine(
        TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres",
        isolation_level="AUTOCOMMIT",
    )
    name = TEST_DATABASE_URL.rsplit("/", 1)[1]
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    yield


@pytest.fixture(autouse=True)
def clean(database):
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE bookings RESTART IDENTITY"))
    engine.dispose()


@pytest.fixture(autouse=True)
def events(monkeypatch):
    """Опубликованные события вместо RabbitMQ."""
    sent = []
    monkeypatch.setattr(
        publisher,
        "publish_threadsafe",
        lambda routing_key, payload: sent.append((routing_key, payload)),
    )
    return sent


@pytest.fixture
def client():
    # без with: lifespan (RabbitMQ, фоновые задачи) не запускается
    return TestClient(app)


def make_token(user_id: int, role: str = "user", **claims) -> dict:
    payload = {
        "sub": str(user_id),
        "role": role,
        "phone": "+996555000111",
        "type": "access",
        "token_type": "access",
        "is_active": True,
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        **claims,
    }
    token = jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin():
    return make_token(1, "admin")


@pytest.fixture
def guest():
    return make_token(42, "user")
