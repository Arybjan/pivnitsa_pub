import asyncio
import uuid

from tests.conftest import FakePublisher, auth, outbox_events, relay


async def test_concurrent_create_same_booking_returns_one_payment(client, bookings):
    bookings.add(5001, user_id=1)
    results = await asyncio.gather(*[
        client.post("/api/v1/payments", json={"booking_id": 5001}, headers=auth(1)) for _ in range(5)
    ])
    assert all(r.status_code == 201 for r in results)
    assert len({r.json()["id"] for r in results}) == 1


async def test_idempotency_key_double_click(client, bookings):
    bookings.add(6001, user_id=10)
    headers = {**auth(10), "Idempotency-Key": str(uuid.uuid4())}
    res1, res2 = await asyncio.gather(
        client.post("/api/v1/payments", json={"booking_id": 6001}, headers=headers),
        client.post("/api/v1/payments", json={"booking_id": 6001}, headers=headers),
    )
    assert res1.json()["id"] == res2.json()["id"]


async def test_idempotency_key_of_other_user_rejected(client, bookings):
    bookings.add(1, user_id=10)
    bookings.add(2, user_id=11)
    key = str(uuid.uuid4())
    assert (await client.post("/api/v1/payments", json={"booking_id": 1}, headers={**auth(10), "Idempotency-Key": key})).status_code == 201
    assert (await client.post("/api/v1/payments", json={"booking_id": 2}, headers={**auth(11), "Idempotency-Key": key})).status_code == 409


async def test_concurrent_pay_emits_single_event(client, bookings):
    bookings.add(7001, user_id=33)
    payment = (await client.post("/api/v1/payments", json={"booking_id": 7001}, headers=auth(33))).json()
    results = await asyncio.gather(*[
        client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(33)) for _ in range(3)
    ])
    assert all(r.json()["status"] == "SUCCEEDED" for r in results)
    assert len(await outbox_events()) == 1


async def test_outbox_waits_for_broker(client, bookings):
    bookings.add(1, user_id=42)
    payment = (await client.post("/api/v1/payments", json={"booking_id": 1}, headers=auth(42))).json()
    await client.post(f"/api/v1/payments/{payment['id']}/pay", headers=auth(42))

    # Брокер недоступен — оплата прошла, событие ждёт в outbox
    assert await relay(FakePublisher(connected=False)) == 0
    assert await relay(FakePublisher(fail=True)) == 0
    assert (await outbox_events())[0]["published"] is False

    # Брокер вернулся — событие уходит
    publisher = FakePublisher()
    assert await relay(publisher) == 1
    assert publisher.published[0]["payload"]["booking_id"] == 1
    assert (await outbox_events())[0]["published"] is True
