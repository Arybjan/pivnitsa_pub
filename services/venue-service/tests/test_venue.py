from datetime import datetime, timedelta, timezone

import jwt
import pytest
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from alembic import command
from app.config import get_settings

START = "2030-08-20T18:00:00Z"
END = "2030-08-21T02:00:00Z"


def availability(client, table_id, **changes):
    response = client.post(
        "/api/v1/tables/availability",
        json={
            "table_ids": [table_id],
            "starts_at": START,
            "ends_at": END,
            **changes,
        },
    )
    assert response.status_code == 200
    return response.json()[0]


def test_health_and_openapi(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/health/ready").status_code == 200
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/tables/availability" in response.json()["paths"]


def test_hall_crud_and_image_clear(client, admin):
    payload = {"name": " VIP ", "map_image_url": "https://example.com/map.png"}
    response = client.post("/api/v1/halls", json=payload, headers=admin)
    assert response.status_code == 201
    hall = response.json()
    assert hall["name"] == "VIP"
    assert client.get(f"/api/v1/halls/{hall['id']}").status_code == 200
    assert len(client.get("/api/v1/halls").json()) == 1
    response = client.patch(
        f"/api/v1/halls/{hall['id']}",
        headers=admin,
        json={
            "name": "Lounge",
            "map_image_url": None,
            "map_width": 800,
        },
    )
    assert response.status_code == 200
    assert response.json()["map_image_url"] is None
    assert response.json()["map_width"] == 800
    assert (
        client.delete(f"/api/v1/halls/{hall['id']}", headers=admin).status_code == 204
    )
    assert client.get(f"/api/v1/halls/{hall['id']}").status_code == 404
    assert client.get("/api/v1/halls").json() == []


def test_duplicate_hall_and_nonempty_delete(client, admin, hall, table):
    assert (
        client.post(
            "/api/v1/halls", json={"name": hall["name"]}, headers=admin
        ).status_code
        == 409
    )
    assert (
        client.delete(f"/api/v1/halls/{hall['id']}", headers=admin).status_code == 409
    )


def test_table_crud_soft_delete_and_number_reuse(client, admin, table, database):
    path = f"/api/v1/tables/{table['id']}"
    response = client.patch(
        path, headers=admin, json={"capacity": 8, "x": 0.5, "rotation": 90}
    )
    assert response.status_code == 200
    assert response.json()["capacity"] == 8
    assert response.json()["hall_id"] == table["hall_id"]
    assert client.get(path).json()["x"] == 0.5
    assert client.delete(path, headers=admin).status_code == 204
    assert client.get(path).status_code == 404
    assert client.get("/api/v1/tables").json() == []
    assert availability(client, table["id"])["reason"] == "NOT_FOUND"
    with database.connect() as connection:
        assert (
            connection.execute(text("SELECT deleted_at FROM venue_tables")).scalar()
            is not None
        )
    response = client.post(
        "/api/v1/tables",
        headers=admin,
        json={
            "hall_id": table["hall_id"],
            "number": 1,
            "capacity": 2,
            "x": 0,
            "y": 1,
        },
    )
    assert response.status_code == 201
    assert response.json()["id"] != table["id"]


def test_number_unique_in_hall_and_filters(client, admin, table):
    payload = {"hall_id": table["hall_id"], "number": 1, "capacity": 6, "x": 0, "y": 0}
    assert client.post("/api/v1/tables", json=payload, headers=admin).status_code == 409
    second_hall = client.post(
        "/api/v1/halls", json={"name": "Second"}, headers=admin
    ).json()
    payload["hall_id"] = second_hall["id"]
    assert client.post("/api/v1/tables", json=payload, headers=admin).status_code == 201
    assert len(client.get("/api/v1/tables", params={"min_capacity": 5}).json()) == 1
    assert (
        len(client.get("/api/v1/tables", params={"hall_id": table["hall_id"]}).json())
        == 1
    )
    assert (
        len(client.get("/api/v1/tables", params={"offset": 1, "limit": 1}).json()) == 1
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"capacity": 0},
        {"capacity": -1},
        {"capacity": True},
        {"number": 0},
        {"number": 2_147_483_648},
        {"x": -0.1},
        {"y": 1.1},
        {"rotation": 360},
        {"status": "BOOKED"},
        {"capacity": None},
        {"hall_id": 2},
        {},
    ],
)
def test_invalid_table_changes(client, admin, table, patch):
    assert (
        client.patch(
            f"/api/v1/tables/{table['id']}", json=patch, headers=admin
        ).status_code
        == 422
    )


@pytest.mark.parametrize("number,status", [(2_147_483_647, 201), (2_147_483_648, 422)])
def test_table_number_storage_range(client, admin, hall, number, status):
    response = client.post(
        "/api/v1/tables",
        headers=admin,
        json={
            "hall_id": hall["id"],
            "number": number,
            "capacity": 4,
            "x": 0,
            "y": 0,
        },
    )
    assert response.status_code == status
    if status == 201:
        assert response.json()["number"] == number


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "  "},
        {"name": None},
        {"map_width": 0},
        {"map_image_url": "file:///tmp/map"},
        {},
    ],
)
def test_invalid_hall_changes(client, admin, hall, payload):
    assert (
        client.patch(
            f"/api/v1/halls/{hall['id']}", json=payload, headers=admin
        ).status_code
        == 422
    )


def test_missing_resources(client, admin):
    assert client.get("/api/v1/halls/999").status_code == 404
    assert client.get("/api/v1/halls/999/map").status_code == 404
    assert client.get("/api/v1/tables/999").status_code == 404
    assert (
        client.post(
            "/api/v1/tables",
            headers=admin,
            json={
                "hall_id": 999,
                "number": 1,
                "capacity": 4,
                "x": 0,
                "y": 0,
            },
        ).status_code
        == 404
    )
    assert availability(client, 999)["reason"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"role": "guest"}, 403),
        ({"is_active": False}, 403),
        ({"exp": 1}, 401),
        ({"token_type": "refresh"}, 401),
        ({"sub": ""}, 401),
        ({"token_type": None}, 401),
        ({"role": "guest", "permissions": "venue:write"}, 403),
    ],
)
def test_rejected_tokens(client, token, changes, code):
    assert (
        client.post(
            "/api/v1/halls", json={"name": "Secret"}, headers=token(**changes)
        ).status_code
        == code
    )


def test_authentication_required_for_all_mutations(client, table, hall):
    actions = [
        ("post", "/api/v1/halls", {"name": "Test"}),
        ("patch", f"/api/v1/halls/{hall['id']}", {"name": "Test"}),
        ("delete", f"/api/v1/halls/{hall['id']}", None),
        (
            "post",
            "/api/v1/tables",
            {"hall_id": hall["id"], "number": 2, "capacity": 2, "x": 0, "y": 0},
        ),
        ("patch", f"/api/v1/tables/{table['id']}", {"capacity": 2}),
        ("delete", f"/api/v1/tables/{table['id']}", None),
        (
            "post",
            f"/api/v1/tables/{table['id']}/blocks",
            {"starts_at": START, "ends_at": END},
        ),
        ("delete", f"/api/v1/tables/{table['id']}/blocks/1", None),
    ]
    for method, path, payload in actions:
        assert client.request(method, path, json=payload).status_code == 401
    assert client.get(f"/api/v1/tables/{table['id']}/blocks").status_code == 401


def test_invalid_signature_and_missing_expiration(client):
    for payload, secret in [
        (
            {"sub": "1", "exp": 9999999999, "role": "admin", "token_type": "access"},
            "wrong-key-that-is-long-enough-for-test",
        ),
        (
            {"sub": "1", "role": "admin", "token_type": "access"},
            get_settings().jwt_secret_key.get_secret_value(),
        ),
    ]:
        encoded = jwt.encode(payload, secret, algorithm="HS256")
        assert (
            client.post(
                "/api/v1/halls",
                json={"name": "Test"},
                headers={"Authorization": f"Bearer {encoded}"},
            ).status_code
            == 401
        )


def test_permission_grants_access(client, token):
    assert (
        client.post(
            "/api/v1/halls",
            json={"name": "Test"},
            headers=token(role="manager", permissions=["venue:write"]),
        ).status_code
        == 201
    )


def test_block_overlap_boundaries_timezone_and_removal(client, admin, table):
    path = f"/api/v1/tables/{table['id']}/blocks"
    response = client.post(
        path,
        headers=admin,
        json={
            "starts_at": "2030-08-20T21:00:00+03:00",
            "ends_at": "2030-08-21T05:00:00+03:00",
            "reason": "Maintenance",
        },
    )
    assert response.status_code == 201
    block = response.json()
    assert block["created_by"] == "3"
    assert availability(client, table["id"])["reason"] == "ADMIN_BLOCK"
    assert availability(
        client, table["id"], starts_at=END, ends_at="2030-08-21T03:00:00Z"
    )["physically_available"]
    assert availability(
        client, table["id"], starts_at="2030-08-20T17:00:00Z", ends_at=START
    )["physically_available"]
    assert client.get(path, headers=admin).json()[0]["id"] == block["id"]
    assert client.delete(f"{path}/{block['id']}", headers=admin).status_code == 204
    assert availability(client, table["id"])["physically_available"]
    assert client.delete(f"{path}/{block['id']}", headers=admin).status_code == 404


def test_overlapping_admin_blocks_are_independent(client, admin, table):
    path = f"/api/v1/tables/{table['id']}/blocks"
    payload = {"starts_at": START, "ends_at": END}
    first = client.post(path, headers=admin, json=payload).json()
    assert client.post(path, headers=admin, json=payload).status_code == 201
    client.delete(f"{path}/{first['id']}", headers=admin)
    assert availability(client, table["id"])["reason"] == "ADMIN_BLOCK"


@pytest.mark.parametrize(
    "interval",
    [
        {"starts_at": END, "ends_at": START},
        {"starts_at": START, "ends_at": START},
        {"starts_at": "2030-08-20T18:00:00", "ends_at": END},
    ],
)
def test_invalid_intervals(client, admin, table, interval):
    assert (
        client.post(
            f"/api/v1/tables/{table['id']}/blocks", headers=admin, json=interval
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/tables/availability", json={"table_ids": [table["id"]], **interval}
        ).status_code
        == 422
    )
    assert (
        client.get(f"/api/v1/halls/{table['hall_id']}/map", params=interval).status_code
        == 422
    )


def test_map_and_physical_state(client, admin, table, hall):
    path = f"/api/v1/halls/{hall['id']}/map"
    assert client.get(path, params={"starts_at": START}).status_code == 422
    data = client.get(path).json()
    assert data["tables"][0]["x"] == 0.25
    assert data["tables"][0]["physically_available"]
    assert data["starts_at"] is None
    assert (
        availability(client, table["id"], guests=5)["reason"] == "INSUFFICIENT_CAPACITY"
    )
    assert availability(client, table["id"], guests=4)["physically_available"]
    client.patch(
        f"/api/v1/tables/{table['id']}", headers=admin, json={"status": "UNAVAILABLE"}
    )
    assert availability(client, table["id"])["reason"] == "TABLE_UNAVAILABLE"
    assert client.get(path).json()["tables"][0]["reason"] == "TABLE_UNAVAILABLE"
    client.patch(
        f"/api/v1/halls/{hall['id']}", headers=admin, json={"is_active": False}
    )
    assert availability(client, table["id"])["reason"] == "HALL_INACTIVE"


def test_current_map_respects_active_block(client, admin, table):
    now = datetime.now(timezone.utc)
    client.post(
        f"/api/v1/tables/{table['id']}/blocks",
        headers=admin,
        json={
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
        },
    )
    data = client.get(f"/api/v1/halls/{table['hall_id']}/map").json()
    assert data["tables"][0]["reason"] == "ADMIN_BLOCK"
    assert availability(client, table["id"])["physically_available"]


def test_block_cannot_be_removed_through_another_table(client, admin, table):
    other = client.post(
        "/api/v1/tables",
        headers=admin,
        json={
            "hall_id": table["hall_id"],
            "number": 2,
            "capacity": 4,
            "x": 0,
            "y": 0,
        },
    ).json()
    block = client.post(
        f"/api/v1/tables/{table['id']}/blocks",
        headers=admin,
        json={"starts_at": START, "ends_at": END},
    ).json()
    assert (
        client.delete(
            f"/api/v1/tables/{other['id']}/blocks/{block['id']}", headers=admin
        ).status_code
        == 404
    )
    assert availability(client, table["id"])["reason"] == "ADMIN_BLOCK"


@pytest.mark.parametrize(
    "assignment", ["capacity = 0", "x = -1", "status = 'BOOKED'", "number = 0"]
)
def test_database_rejects_invalid_table_state(database, table, assignment):
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(text(f"UPDATE venue_tables SET {assignment}"))


def test_migration_round_trip_and_model_match(database):
    config = Config("alembic.ini")
    command.check(config)
    assert set(inspect(database).get_table_names()) >= {
        "halls",
        "venue_tables",
        "table_blocks",
    }
    command.downgrade(config, "base")
    assert "halls" not in inspect(database).get_table_names()
    command.upgrade(config, "head")
    command.check(config)
