from datetime import datetime, timedelta, timezone

from tests.test_admin_bookings import URL


def future(days: int = 1, hour: int = 14) -> str:
    # 14:00 UTC = 20:00 по Бишкеку, тот же календарный день
    moment = datetime.now(timezone.utc) + timedelta(days=days)
    return moment.replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


def book(client, headers, **body):
    return client.post(URL, headers=headers, json={"table_id": 5, "guests": 2, **body})


def test_booking_without_event(client, guest):
    starts_at = future()
    response = book(client, guest, starts_at=starts_at)
    assert response.status_code == 201, response.text

    booking = response.json()
    assert booking["event_id"] is None
    assert datetime.fromisoformat(booking["starts_at"]) == datetime.fromisoformat(starts_at)
    assert booking["booking_date"] == starts_at[:10]
    assert booking["status"] == "PENDING_PAYMENT"


def test_booking_with_event_still_works(client, guest):
    response = book(client, guest, event_id=3)
    assert response.status_code == 201, response.text
    assert response.json()["event_id"] == 3


def test_event_or_starts_at_required(client, guest):
    assert book(client, guest).status_code == 422


def test_event_and_starts_at_together_rejected(client, guest):
    assert book(client, guest, event_id=3, starts_at=future()).status_code == 422


def test_starts_at_in_past_rejected(client, guest):
    assert book(client, guest, starts_at=future(days=-1)).status_code == 422


def test_starts_at_needs_timezone(client, guest):
    assert book(client, guest, starts_at=future()[:19]).status_code == 422


def test_same_table_same_day_conflict(client, guest):
    assert book(client, guest, starts_at=future(hour=13)).status_code == 201

    response = book(client, guest, starts_at=future(hour=16))
    assert response.status_code == 409
    assert response.json()["detail"] == "Table is already booked for this date"


def test_other_day_no_conflict(client, guest):
    assert book(client, guest, starts_at=future(days=1)).status_code == 201
    assert book(client, guest, starts_at=future(days=2)).status_code == 201
