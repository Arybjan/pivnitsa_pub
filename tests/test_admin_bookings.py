from tests.conftest import make_token

URL = "/api/v1/bookings"

# 23:30 по Бишкеку (UTC+6) - уже следующий день по UTC
EVENING = "2026-12-20T17:30:00Z"


def admin_booking(**overrides):
    data = {
        "table_id": 1,
        "starts_at": "2026-12-20T14:00:00Z",
        "guests": 4,
        "guest_name": "Алексей",
        "guest_phone": "+996 555 123456",
        "total_amount": "5000",
        "prepayment": "1000",
        "prepayment_paid": True,
    }
    data.update(overrides)
    return data


def test_admin_creates_confirmed_booking_without_event(client, admin, events):
    response = client.post(f"{URL}/admin", headers=admin, json=admin_booking())
    assert response.status_code == 201, response.text
    booking = response.json()
    assert booking["status"] == "CONFIRMED"
    assert booking["source"] == "ADMIN"
    assert booking["event_id"] is None
    assert booking["booking_date"] == "2026-12-20"
    assert booking["guest_name"] == "Алексей"
    assert booking["phone"] == "+996 555 123456"
    assert float(booking["total_amount"]) == 5000
    assert events[-1][0] == "booking.confirmed"
    assert events[-1][1]["source"] == "ADMIN"


def test_booking_date_uses_venue_timezone(client, admin):
    response = client.post(f"{URL}/admin", headers=admin, json=admin_booking(starts_at=EVENING))
    assert response.json()["booking_date"] == "2026-12-20"


def test_same_table_same_day_rejected(client, admin):
    assert client.post(f"{URL}/admin", headers=admin, json=admin_booking()).status_code == 201
    response = client.post(f"{URL}/admin", headers=admin, json=admin_booking(starts_at=EVENING))
    assert response.status_code == 409
    assert response.json()["detail"] == "Table is already booked for this date"
    # другой стол и другой день - можно
    assert client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=2)).status_code == 201
    assert client.post(
        f"{URL}/admin", headers=admin, json=admin_booking(starts_at="2026-12-21T14:00:00Z")
    ).status_code == 201


def test_event_and_plain_booking_conflict_on_same_day(client, admin):
    assert client.post(f"{URL}/admin", headers=admin, json=admin_booking(event_id=7)).status_code == 201
    assert client.post(f"{URL}/admin", headers=admin, json=admin_booking()).status_code == 409
    # тот же стол на то же мероприятие
    response = client.post(f"{URL}/admin", headers=admin, json=admin_booking(event_id=7))
    assert response.json()["detail"] == "Table is already booked for this event"
    # другое мероприятие в тот же день - можно
    assert client.post(f"{URL}/admin", headers=admin, json=admin_booking(event_id=8)).status_code == 201


def test_rebooking_after_cancel(client, admin):
    booking = client.post(f"{URL}/admin", headers=admin, json=admin_booking()).json()
    response = client.post(f"{URL}/{booking['id']}/cancel", headers=admin, json={"reason": "Гость отменил"})
    assert response.status_code == 200
    assert response.json()["cancel_reason"] == "Гость отменил"
    assert client.post(f"{URL}/admin", headers=admin, json=admin_booking()).status_code == 201


def test_list_filters(client, admin):
    client.post(f"{URL}/admin", headers=admin, json=admin_booking())
    client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=2, event_id=7))
    client.post(f"{URL}/admin", headers=admin, json=admin_booking(starts_at="2026-12-22T14:00:00Z"))
    cancelled = client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=3)).json()
    client.post(f"{URL}/{cancelled['id']}/cancel", headers=admin)

    by_date = client.get(URL, headers=admin, params={"date_from": "2026-12-20", "date_to": "2026-12-20"}).json()
    assert len(by_date) == 3
    active = client.get(URL, headers=admin, params={"date_from": "2026-12-20", "date_to": "2026-12-20", "active": True}).json()
    assert {b["table_id"] for b in active} == {1, 2}
    by_event = client.get(URL, headers=admin, params=[("event_id", 7), ("event_id", 99)]).json()
    assert [b["table_id"] for b in by_event] == [2]
    by_table = client.get(URL, headers=admin, params={"table_id": 1, "active": True}).json()
    assert len(by_table) == 2


def test_update_booking(client, admin):
    booking = client.post(f"{URL}/admin", headers=admin, json=admin_booking()).json()
    other = client.post(f"{URL}/admin", headers=admin, json=admin_booking(table_id=2)).json()

    response = client.patch(f"{URL}/{booking['id']}", headers=admin, json={"guests": 6, "guest_name": "Мария"})
    assert response.status_code == 200
    assert (response.json()["guests"], response.json()["guest_name"]) == (6, "Мария")

    # перенос на занятый стол
    response = client.patch(f"{URL}/{booking['id']}", headers=admin, json={"table_id": 2})
    assert response.status_code == 409
    # перенос на другой день меняет booking_date
    response = client.patch(f"{URL}/{booking['id']}", headers=admin, json={"starts_at": "2026-12-25T14:00:00Z"})
    assert response.json()["booking_date"] == "2026-12-25"
    # теперь стол 2 на 20-е можно занять переносом второй брони на стол 1
    assert client.patch(f"{URL}/{other['id']}", headers=admin, json={"table_id": 1}).status_code == 200

    # предоплата больше суммы
    response = client.patch(f"{URL}/{booking['id']}", headers=admin, json={"prepayment": "9000"})
    assert response.status_code == 409


def test_update_validation(client, admin):
    booking = client.post(f"{URL}/admin", headers=admin, json=admin_booking()).json()
    path = f"{URL}/{booking['id']}"
    assert client.patch(path, headers=admin, json={}).status_code == 422
    assert client.patch(path, headers=admin, json={"guests": None}).status_code == 422
    assert client.patch(path, headers=admin, json={"starts_at": "2026-12-25T14:00:00"}).status_code == 422
    client.post(f"{path}/cancel", headers=admin)
    assert client.patch(path, headers=admin, json={"guests": 2}).status_code == 409


def test_create_validation(client, admin):
    for bad in (
        {"prepayment": "6000"},
        {"guest_name": ""},
        {"guest_phone": "abc"},
        {"guests": 0},
        {"starts_at": "2026-12-20T14:00:00"},
        {"status": "CANCELLED"},
    ):
        response = client.post(f"{URL}/admin", headers=admin, json=admin_booking(**bad))
        assert response.status_code == 422, bad


def test_admin_endpoints_require_admin(client, guest):
    assert client.get(URL, headers=guest).status_code == 403
    assert client.post(f"{URL}/admin", headers=guest, json=admin_booking()).status_code == 403
    assert client.patch(f"{URL}/1", headers=guest, json={"guests": 2}).status_code == 403
    assert client.get(URL).status_code in (401, 403)


def test_admin_can_read_and_cancel_guest_booking(client, admin, guest, events):
    booking = client.post(URL, headers=guest, json={"table_id": 5, "event_id": 3, "guests": 2}).json()
    assert booking["source"] == "APP" and booking["starts_at"] is None

    assert client.get(f"{URL}/{booking['id']}", headers=admin).status_code == 200
    assert client.get(f"{URL}/{booking['id']}", headers=make_token(77)).status_code == 403
    # чужой гость не может отменить
    assert client.post(f"{URL}/{booking['id']}/cancel", headers=make_token(77)).status_code == 404

    response = client.post(f"{URL}/{booking['id']}/cancel", headers=admin, json={"reason": "Ошибка при записи"})
    assert response.status_code == 200
    assert events[-1][0] == "booking.cancelled"
    assert events[-1][1]["reason"] == "admin"


def test_guest_cancel_without_body_still_works(client, guest, events):
    booking = client.post(URL, headers=guest, json={"table_id": 5, "event_id": 3, "guests": 2}).json()
    response = client.post(f"{URL}/{booking['id']}/cancel", headers=guest)
    assert response.status_code == 200
    assert response.json()["cancel_reason"] is None
    assert events[-1][1]["reason"] == "user"
