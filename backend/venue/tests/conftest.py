import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.config import get_settings
from app.database import create_database_engine, get_db
from app.main import app


@pytest.fixture
def database(tmp_path, monkeypatch):
    postgres = os.environ.get("TEST_DATABASE_URL")
    admin_engine = None
    schema = "venue_test_" + uuid4().hex
    if postgres:
        admin_engine = create_engine(postgres, isolation_level="AUTOCOMMIT")
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        url = make_url(postgres).update_query_dict(
            {"options": f"-csearch_path={schema}"}
        )
        url = url.render_as_string(hide_password=False)
    else:
        url = f"sqlite:///{tmp_path / 'venue.db'}"
    monkeypatch.setattr(get_settings(), "database_url", url)
    engine = create_database_engine(url)
    try:
        command.upgrade(Config("alembic.ini"), "head")
        yield engine
    finally:
        engine.dispose()
        if admin_engine is not None:
            with admin_engine.connect() as connection:
                connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            admin_engine.dispose()


@pytest.fixture
def client(database):
    def override_db():
        with Session(database, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def token():
    def make_token(**changes):
        payload = {
            "sub": "3",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "role": "admin",
            "token_type": "access",
            **changes,
        }
        encoded = jwt.encode(
            payload, get_settings().jwt_secret_key.get_secret_value(), algorithm="HS256"
        )
        return {"Authorization": f"Bearer {encoded}"}

    return make_token


@pytest.fixture
def admin(token):
    return token()


@pytest.fixture
def hall(client, admin):
    response = client.post("/api/v1/halls", json={"name": "Main hall"}, headers=admin)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def table(client, admin, hall):
    response = client.post(
        "/api/v1/tables",
        headers=admin,
        json={
            "hall_id": hall["id"],
            "number": 1,
            "capacity": 4,
            "x": 0.25,
            "y": 0.75,
        },
    )
    assert response.status_code == 201
    return response.json()
