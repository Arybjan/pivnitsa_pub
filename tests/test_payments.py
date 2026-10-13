import pytest
import sqlalchemy as sa

from app.core.database import async_session_maker
from app.messaging.consumer import handle_booking_event
from app.models.payment import Payment, PaymentStatus
from app.services.payment_service import payment_service
from tests.conftest import FakePublisher, auth, make_token, outbox_events, relay


async def create(client, booking_id, user_id, **headers):
    return await client.post("/api/v1/payments", json={"booking_id": booking_id}, headers={**auth(user_id), **headers})


async def test_health_check(client):
    res = await client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "payment-service"


async def test_migrations_match_models():
    # Именно это расхождение (нет idempotency_key в миграции) роняло POST /payments с 500
    async with async_session_maker() as session:
        def columns(sync_conn):
            inspector = sa.inspect(sync_conn)
            return {table: {c["name"] for c in inspector.get_columns(table)} for table in ("payments", "outbox_events")}

        db_columns = await (await session.connection()).run_sync(columns)

    for table in Payment.metadata.sorted_tables:
        if table.name in db_columns:
            assert {c.name for c in table.columns} == db_columns[table.name], table.name


async def test_requires_valid_token(client, bookings):
    bookings.add(1, user_id=42)
    assert (await client.post("/api/v1/payments", json={"booking_id": 1})).status_code == 401
    no_exp = {"Authorization": f"Bearer {make_token(42, exp=False)}"}
    assert (await client.post("/api/v1/payments", json={"booking_id": 1}, headers=no_exp)).status_code == 401


async def test_amount_and_user_come_from_server(client, bookings):
    bookings.add(1, user_id=42, guests=3)
    # Попытка подсунуть сумму и чужого пользователя игнорируется
    res = await client.post(
        "/api/v1/payments",
        json={"booking_id": 1, "amount": "0.01", "user_id": 7},
        headers=auth(42),
    )
    assert res.status_code == 201
    data = res.json()
    assert data["user_id"] == 42
    assert data["amount"] == "3000.00"
    assert data["currency"] == "KGS"
    assert data["status"] == "PENDING"
    assert data["client_secret"]
    assert data["checkout_url"] == f"/api/v1/payments/{data['id']}/checkout?secret={data['client_secret']}"


@pytest.mark.parametrize(
    "setup, expected",
    [
        (lambda b: b.add(1, user_id=99), 403),
        (lambda b: None, 404),
        (lambda b: b.add(1, user_id=42, status="CONFIRMED"), 409),
        (lambda b: b.add(1, user_id=42, status="EXPIRED"), 409),
        (lambda b: b.add(1, user_id=42, minutes_left=-1), 409),
    ],
    ids=["other_users_booking", "missing_booking", "already_confirmed", "expired_status", "hold_elapsed"],
)
async def test_booking_must_be_payable(client, bookings, setup, expected):
    setup(bookings)
    assert (await create(client, 1, 42)).status_code == expected


async def test_booking_service_down_returns_503(client, bookings):
    bookings.unavailable = True
    assert (await create(client, 1, 42)).status_code == 503


async def test_pay_flow_emits_payment_succeeded_once(client, bookings):
    bookings.add(101, user_id=42, guests=2)
    payment = (await create(client, 101, 42)).json()

    res = await client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(42))
    assert res.status_code == 200
    assert res.json()["status"] == "SUCCEEDED"
    assert res.json()["receipt_url"]
    assert res.json()["client_secret"] is None

    # Повторное нажатие не создаёт второе событие
    assert (await client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(42))).status_code == 200

    events = await outbox_events()
    assert [e["routing_key"] for e in events] == ["payment.succeeded"]
    payload = events[0]["payload"]
    assert (payload["booking_id"], payload["user_id"], payload["amount"]) == (101, 42, "2000.00")

    publisher = FakePublisher()
    assert await relay(publisher) == 1
    assert await relay(publisher) == 0
    assert publisher.published[0]["routing_key"] == "payment.succeeded"

    # Оплаченную бронь нельзя оплатить снова
    assert (await create(client, 101, 42)).status_code == 409


async def test_other_user_cannot_see_or_pay(client, bookings):
    bookings.add(1, user_id=42)
    payment = (await create(client, 1, 42)).json()

    assert (await client.get(f"/api/v1/payments/{payment['id']}", headers=auth(7))).status_code == 404
    assert (await client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(7))).status_code == 404
    assert (await client.post(f"/api/v1/payments/{payment['id']}/pay")).status_code == 401

    admin_view = await client.get(f"/api/v1/payments/{payment['id']}", headers=auth(1, "admin"))
    assert admin_view.status_code == 200
    assert admin_view.json()["client_secret"] is None


async def test_checkout_page_requires_secret_and_escapes(client, bookings):
    bookings.add(1, user_id=42)
    payment = (await create(client, 1, 42)).json()
    url = f"/api/v1/payments/{payment['id']}/checkout"

    assert (await client.get(url)).status_code == 422
    assert (await client.get(url, params={"secret": "wrong"})).status_code == 404

    async with async_session_maker() as session:
        await session.execute(
            sa.update(Payment).where(Payment.id == payment["id"]).values(provider="<script>alert(1)</script>")
        )
        await session.commit()

    page = await client.get(url, params={"secret": payment["client_secret"]})
    assert page.status_code == 200
    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;" in page.text

    # Кнопка страницы платит по секрету, без токена
    paid = await client.post(f"/api/v1/payments/{payment['id']}/pay", headers={"X-Client-Secret": payment["client_secret"]})
    assert paid.json()["status"] == "SUCCEEDED"


async def test_list_my_payments(client, bookings):
    bookings.add(1, user_id=42)
    bookings.add(2, user_id=7)
    await create(client, 1, 42)
    await create(client, 2, 7)
    mine = (await client.get("/api/v1/payments/my", headers=auth(42))).json()
    assert [p["booking_id"] for p in mine] == [1]


async def test_refund_is_admin_only_and_emits_event(client, bookings):
    bookings.add(1, user_id=42)
    payment = (await create(client, 1, 42)).json()
    await client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(42))

    assert (await client.post(f"/api/v1/payments/{payment['id']}/refund", headers=auth(42))).status_code == 403
    assert (await client.post(f"/api/v1/payments/{payment['id']}/refund")).status_code == 401

    res = await client.post(f"/api/v1/payments/{payment['id']}/refund", json={"reason": "guest_request"}, headers=auth(1, "admin"))
    assert res.status_code == 200
    assert res.json()["status"] == "REFUNDED"
    assert res.json()["refund_reason"] == "guest_request"
    assert [e["routing_key"] for e in await outbox_events()] == ["payment.succeeded", "payment.refunded"]

    # После возврата бронь снова можно оплатить (если Booking Service позволит)
    assert (await create(client, 1, 42)).status_code == 201


async def test_refund_pending_payment_fails(client, bookings):
    bookings.add(1, user_id=42)
    payment = (await create(client, 1, 42)).json()
    res = await client.post(f"/api/v1/payments/{payment['id']}/refund", headers=auth(1, "admin"))
    assert res.status_code == 400


async def test_gateway_refund_failure_is_retried(client, bookings, monkeypatch):
    bookings.add(1, user_id=42)
    payment = (await create(client, 1, 42)).json()
    await client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(42))

    async def broken_refund(*args, **kwargs):
        raise RuntimeError("gateway timeout")

    monkeypatch.setattr(payment_service.gateway, "refund", broken_refund)
    res = await client.post(f"/api/v1/payments/{payment['id']}/refund", headers=auth(1, "admin"))
    assert res.json()["status"] == "REFUND_PENDING"

    monkeypatch.undo()
    async with async_session_maker() as session:
        assert await payment_service.retry_pending_refunds(session) == 1
    final = await client.get(f"/api/v1/payments/{payment['id']}", headers=auth(42))
    assert final.json()["status"] == "REFUNDED"


@pytest.mark.parametrize(
    "routing_key, extra, expected_status",
    [
        ("booking.payment_rejected", {"reason": "booking_expired"}, "REFUNDED"),
        ("booking.cancelled", {"previous_status": "CONFIRMED", "reason": "event_cancelled"}, "REFUNDED"),
        ("booking.cancelled", {"previous_status": "PENDING_PAYMENT", "reason": "user"}, "SUCCEEDED"),
    ],
    ids=["payment_rejected", "paid_booking_cancelled", "unpaid_booking_cancelled"],
)
async def test_booking_events_trigger_refunds(client, bookings, routing_key, extra, expected_status):
    bookings.add(1, user_id=42)
    payment = (await create(client, 1, 42)).json()
    await client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(42))

    await handle_booking_event(routing_key, {"booking_id": 1, **extra})
    # Повторная доставка события не делает второй возврат
    await handle_booking_event(routing_key, {"booking_id": 1, **extra})

    res = await client.get(f"/api/v1/payments/{payment['id']}", headers=auth(42))
    assert res.json()["status"] == expected_status
    refunds = [e for e in await outbox_events() if e["routing_key"] == "payment.refunded"]
    assert len(refunds) == (1 if expected_status == "REFUNDED" else 0)


async def test_webhook_confirms_once(client, bookings):
    bookings.add(1, user_id=42)
    payment = (await create(client, 1, 42)).json()
    webhook = {
        "type": "payment_intent.succeeded",
        "data": {"object": {
            "id": payment["provider_payment_id"],
            "metadata": {"payment_id": str(payment["id"])},
            "charges": {"data": [{"receipt_url": "https://stripe.com/receipts/test_123"}]},
        }},
    }
    assert (await client.post("/api/v1/payments/webhook", json=webhook)).json()["status"] == "confirmed"
    assert (await client.post("/api/v1/payments/webhook", json=webhook)).json()["status"] == "already_processed"

    res = await client.get(f"/api/v1/payments/{payment['id']}", headers=auth(42))
    assert res.json()["receipt_url"] == "https://stripe.com/receipts/test_123"
    assert len(await outbox_events()) == 1


async def test_unsigned_webhook_rejected_outside_sandbox(client, monkeypatch):
    monkeypatch.setattr(payment_service.gateway, "is_sandbox", False)
    res = await client.post("/api/v1/payments/webhook", json={"type": "payment_intent.succeeded"})
    assert res.status_code == 400


async def test_failed_payment_allows_retry(client, bookings, monkeypatch):
    bookings.add(1, user_id=42)
    payment = (await create(client, 1, 42)).json()

    async def declined(*args, **kwargs):
        return {"status": "requires_payment_method"}

    monkeypatch.setattr(payment_service.gateway, "confirm_payment", declined)
    res = await client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(42))
    assert res.json()["status"] == "FAILED"
    assert [e["routing_key"] for e in await outbox_events()] == ["payment.failed"]

    retry = await create(client, 1, 42)
    assert retry.status_code == 201
    assert retry.json()["id"] != payment["id"]
