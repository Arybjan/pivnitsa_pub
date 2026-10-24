import subprocess
import sys

import httpx
import pytest
import respx
from sqlalchemy import create_engine, text

from app.services import venue_client
from tests.conftest import TEST_DATABASE_URL, make_token
from tests.test_admin_bookings import admin_booking

URL = "/api/v1/bookings"
VENUE = "http://venue.test"


def guest_booking(client, headers, **overrides):
    body = {"table_id": 1, "event_id": 3, "guests": 2, **overrides}
    return client.post(URL, headers=headers, json=body)


@pytest.fixture
def venue(monkeypatch):
    """Venue Service: столу с ID n назначен номер n + 10."""
    monkeypatch.setattr(venue_client, "VENUE_SERVICE_URL", VENUE)

    def tables(request):
        ids = [int(value) for value in request.url.params.get_list("id")]
        return httpx.Response(200, json=[{"id": i, "number": i + 10} for i in ids])

    with respx.mock(assert_all_called=False) as mock:
        yield mock.get(f"{VENUE}/api/v1/tables").mock(side_effect=tables)


# --- comment ---


def test_comment_saved_and_returned(client, guest):
    response = guest_booking(client, guest, comment="  Столик у окна  ")
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["comment"] == "Столик у окна"
    assert client.get(f"{URL}/{booking['id']}", headers=guest).json()["comment"] == "Столик у окна"
    assert client.get(f"{URL}/my", headers=guest).json()[0]["comment"] == "Столик у окна"


@pytest.mark.parametrize("comment", ["", "   ", None, "omitted"])
def test_empty_comment_is_null(client, guest, comment):
    body = {} if comment == "omitted" else {"comment": comment}
    response = guest_booking(client, guest, **body)
    assert response.status_code == 201, response.text
    assert response.json()["comment"] is None


def test_comment_length_limit(client, guest):
    response = guest_booking(client, guest, comment="я" * 500)
    assert response.status_code == 201
    assert len(response.json()["comment"]) == 500

    response = guest_booking(client, guest, table_id=2, comment="я" * 501)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "comment"]


def test_comment_must_be_string(client, guest):
    assert guest_booking(client, guest, comment=123).status_code == 422


# --- table_number ---


def test_table_number_in_all_responses(client, admin, guest, venue):
    created = guest_booking(client, guest, table_id=5).json()
    assert (created["table_id"], created["table_number"]) == (5, 15)

    assert client.get(f"{URL}/{created['id']}", headers=guest).json()["table_number"] == 15
    assert client.get(f"{URL}/my", headers=guest).json()[0]["table_number"] == 15

    response = client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=7))
    admin_created = response.json()
    assert admin_created["table_number"] == 17

    updated = client.patch(f"{URL}/{admin_created['id']}", headers=admin, json={"table_id": 8}).json()
    assert updated["table_number"] == 18

    confirmed = client.post(f"{URL}/{created['id']}/confirm", headers=admin).json()
    assert confirmed["table_number"] == 15
    cancelled = client.post(f"{URL}/{created['id']}/cancel", headers=guest).json()
    assert cancelled["table_number"] == 15

    listed = client.get(URL, headers=admin).json()
    assert {(b["table_id"], b["table_number"]) for b in listed} == {(5, 15), (8, 18)}


def test_booking_list_loads_table_numbers_in_one_request(client, admin, venue):
    for table_id in range(1, 6):
        client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=table_id))
    client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=1, starts_at="2026-12-22T14:00:00Z"))
    calls_before = venue.call_count

    listed = client.get(URL, headers=admin).json()

    assert len(listed) == 6
    assert all(b["table_number"] == b["table_id"] + 10 for b in listed)
    # Без N+1: один запрос к Venue, каждый стол - один раз
    assert venue.call_count - calls_before == 1
    assert venue.calls.last.request.url.params.get_list("id") == ["1", "2", "3", "4", "5"]


def test_table_number_lookup_is_batched(monkeypatch):
    monkeypatch.setattr(venue_client, "VENUE_SERVICE_URL", VENUE)
    with respx.mock:
        route = respx.get(f"{VENUE}/api/v1/tables").mock(
            side_effect=lambda request: httpx.Response(
                200,
                json=[{"id": int(i), "number": int(i)} for i in request.url.params.get_list("id")],
            )
        )
        numbers = venue_client.get_table_numbers(list(range(1, 451)))
    assert len(numbers) == 450
    assert route.call_count == 3


def test_missing_table_or_venue_down_gives_null_number(client, admin, monkeypatch):
    client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=4))

    # Venue не настроен
    assert client.get(URL, headers=admin).json()[0]["table_number"] is None

    monkeypatch.setattr(venue_client, "VENUE_SERVICE_URL", VENUE)
    with respx.mock:
        # Стол удалён: Venue его не возвращает
        respx.get(f"{VENUE}/api/v1/tables").mock(return_value=httpx.Response(200, json=[]))
        assert client.get(URL, headers=admin).json()[0]["table_number"] is None
    with respx.mock:
        respx.get(f"{VENUE}/api/v1/tables").mock(side_effect=httpx.ConnectError("down"))
        response = client.get(URL, headers=admin)
        assert response.status_code == 200
        assert response.json()[0]["table_number"] is None
    with respx.mock:
        respx.get(f"{VENUE}/api/v1/tables").mock(return_value=httpx.Response(500))
        assert client.get(URL, headers=admin).json()[0]["table_number"] is None


# --- авторизация по access token ---


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-jwt"},
        make_token(42, type="refresh", token_type="refresh"),
        make_token(42, type=None, token_type=None),
        make_token(42, sub=None),
    ],
)
def test_user_endpoints_require_valid_access_token(client, headers):
    for method, path in [
        ("post", URL),
        ("get", f"{URL}/my"),
        ("get", f"{URL}/1"),
        ("post", f"{URL}/1/cancel"),
    ]:
        response = client.request(method, path, headers=headers, json={"table_id": 1, "event_id": 3, "guests": 2})
        assert response.status_code == 401, (method, path, response.text)


def test_inactive_account_rejected(client):
    response = guest_booking(client, make_token(42, is_active=False))
    assert response.status_code == 403


def test_owner_comes_from_token_not_body(client, guest):
    response = guest_booking(client, guest, user_id=1)
    assert response.status_code == 201
    assert response.json()["user_id"] == 42


def test_user_cannot_read_or_cancel_foreign_booking(client, guest, events):
    booking = guest_booking(client, guest).json()
    stranger = make_token(77)

    assert client.get(f"{URL}/{booking['id']}", headers=stranger).status_code == 403
    assert client.post(f"{URL}/{booking['id']}/cancel", headers=stranger).status_code == 404
    assert client.get(f"{URL}/my", headers=stranger).json() == []
    # user_id в query игнорируется
    assert client.get(f"{URL}/my", headers=stranger, params={"user_id": 42}).json() == []
    assert client.get(f"{URL}/{booking['id']}", headers=guest).json()["status"] == "PENDING_PAYMENT"


# --- миграция ---


def alembic(*args):
    result = subprocess.run([sys.executable, "-m", "alembic", *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_comment_migration_keeps_existing_bookings(client, guest):
    booking = guest_booking(client, guest, comment="У окна").json()
    engine = create_engine(TEST_DATABASE_URL)
    try:
        alembic("downgrade", "d5f1a7c9e2b8")
        alembic("upgrade", "head")
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT id, table_id, guests, comment FROM bookings")
            ).one()
    finally:
        engine.dispose()
    assert (row.id, row.table_id, row.guests, row.comment) == (booking["id"], 1, 2, None)
