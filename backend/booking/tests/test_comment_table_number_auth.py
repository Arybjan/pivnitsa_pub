from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx
from sqlalchemy import text

from app.database import engine
from app.services import venue_client
from tests.conftest import make_token
from tests.test_admin_bookings import URL, admin_booking

VENUE = "http://venue.test"
NUMBERS = f"{VENUE}/api/v1/tables/numbers"


def book(client, headers, **overrides):
    body = {"table_id": 5, "event_id": 3, "guests": 2}
    body.update(overrides)
    return client.post(URL, headers=headers, json=body)


# ---- comment ----


def test_comment_saved_and_returned(client, guest):
    response = book(client, guest, comment="  У окна, будет торт  ")
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["comment"] == "У окна, будет торт"

    assert client.get(f"{URL}/{booking['id']}", headers=guest).json()["comment"] == "У окна, будет торт"
    assert client.get(f"{URL}/my", headers=guest).json()[0]["comment"] == "У окна, будет торт"

    with engine.connect() as connection:
        stored = connection.execute(text("SELECT comment FROM bookings")).scalar_one()
    assert stored == "У окна, будет торт"


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_comment_stored_as_null(client, guest, value):
    response = book(client, guest, comment=value)
    assert response.status_code == 201, response.text
    assert response.json()["comment"] is None


def test_comment_is_optional(client, guest):
    response = book(client, guest)
    assert response.status_code == 201
    assert response.json()["comment"] is None


def test_comment_length_limit(client, guest):
    assert book(client, guest, comment="я" * 500).json()["comment"] == "я" * 500

    response = book(client, guest, table_id=6, comment="я" * 501)
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["loc"] == ["body", "comment"]
    assert error["type"] == "string_too_long"


def test_comment_must_be_string(client, guest):
    assert book(client, guest, comment=123).status_code == 422


# ---- table_number ----


@pytest.fixture
def venue(monkeypatch):
    monkeypatch.setattr(venue_client, "VENUE_SERVICE_URL", VENUE)
    with respx.mock(assert_all_called=False) as mock:
        yield mock


def test_table_number_in_single_booking_responses(client, guest, admin, venue):
    route = venue.get(NUMBERS).mock(return_value=httpx.Response(200, json=[{"id": 5, "number": 15}]))

    created = book(client, guest).json()
    assert created["table_id"] == 5
    assert created["table_number"] == 15

    assert client.get(f"{URL}/{created['id']}", headers=guest).json()["table_number"] == 15
    assert client.post(f"{URL}/{created['id']}/confirm", headers=admin).json()["table_number"] == 15
    assert client.post(f"{URL}/{created['id']}/cancel", headers=guest).json()["table_number"] == 15
    assert route.calls.last.request.url.params.get_list("id") == ["5"]


def test_table_numbers_fetched_once_per_list(client, admin, venue):
    route = venue.get(NUMBERS).mock(
        return_value=httpx.Response(200, json=[{"id": 1, "number": 11}, {"id": 2, "number": 12}])
    )
    for table_id in (1, 2, 3):
        client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=table_id))
    client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=1, starts_at="2026-12-21T14:00:00Z"))

    route.reset()
    response = client.get(URL, headers=admin)

    assert response.status_code == 200
    # Один запрос к Venue на весь список (без N+1), повторяющийся стол - один раз
    assert route.call_count == 1
    assert sorted(route.calls.last.request.url.params.get_list("id")) == ["1", "2", "3"]
    numbers = {(b["table_id"], b["table_number"]) for b in response.json()}
    # Стола 3 нет в Venue: table_id остаётся, номер null
    assert numbers == {(1, 11), (2, 12), (3, None)}


@pytest.mark.parametrize(
    "venue_response",
    [
        httpx.Response(500),
        httpx.Response(200, json={"unexpected": True}),
        httpx.ConnectError("down"),
    ],
)
def test_booking_still_returned_when_venue_fails(client, guest, venue, venue_response):
    if isinstance(venue_response, Exception):
        venue.get(NUMBERS).mock(side_effect=venue_response)
    else:
        venue.get(NUMBERS).mock(return_value=venue_response)

    response = book(client, guest)
    assert response.status_code == 201
    assert response.json()["table_id"] == 5
    assert response.json()["table_number"] is None
    assert client.get(f"{URL}/my", headers=guest).json()[0]["table_number"] is None


def test_table_number_null_without_venue_url(client, guest):
    assert venue_client.VENUE_SERVICE_URL == ""
    assert book(client, guest).json()["table_number"] is None


def test_my_bookings_without_bookings_does_not_call_venue(client, guest, venue):
    route = venue.get(NUMBERS)
    assert client.get(f"{URL}/my", headers=guest).json() == []
    assert route.call_count == 0


# ---- access token ----


def expired(user_id=42):
    return make_token(user_id, exp=datetime.now(timezone.utc) - timedelta(minutes=1))


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": "Basic Zm9vOmJhcg=="},
        make_token(42, type="refresh", token_type="refresh"),
        make_token(42, type="service", token_type="service"),
        make_token(42, type=None, token_type=None),
        make_token(0),
        make_token("abc"),
    ],
    ids=["no-header", "garbage", "basic", "refresh", "service", "no-type", "zero-sub", "text-sub"],
)
def test_invalid_token_rejected_with_401(client, headers):
    for method, path in [("GET", f"{URL}/my"), ("POST", URL), ("GET", f"{URL}/1"), ("POST", f"{URL}/1/cancel")]:
        json = {"table_id": 5, "event_id": 3, "guests": 2} if method == "POST" else None
        response = client.request(method, path, headers=headers, json=json)
        assert response.status_code == 401, (method, path, response.text)


def test_expired_token_rejected(client):
    assert client.get(f"{URL}/my", headers=expired()).status_code == 401


def test_wrong_secret_rejected(client):
    from jose import jwt

    token = jwt.encode(
        {"sub": "42", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        "another-secret-that-is-long-enough-123",
        algorithm="HS256",
    )
    assert client.get(f"{URL}/my", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_inactive_user_rejected(client):
    assert client.get(f"{URL}/my", headers=make_token(42, is_active=False)).status_code == 403


def test_user_sees_only_own_bookings(client, guest):
    mine = book(client, guest).json()
    other = make_token(77)
    foreign = book(client, other, table_id=6).json()

    # user_id в query не влияет: пользователь берётся из токена
    my = client.get(f"{URL}/my", params={"user_id": 77}, headers=guest).json()
    assert [b["id"] for b in my] == [mine["id"]]

    assert client.get(f"{URL}/{foreign['id']}", headers=guest).status_code == 403
    assert client.post(f"{URL}/{foreign['id']}/cancel", headers=guest).status_code == 404
    assert client.get(f"{URL}/{foreign['id']}", headers=other).json()["status"] == "PENDING_PAYMENT"
