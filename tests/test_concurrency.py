import asyncio
import uuid
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_concurrent_payments_different_users_prevented(client: AsyncClient):
    """
    Scenario: User 1 and User 2 both try to pay for the exact same booking #5001 at the same millisecond.
    Only ONE user may proceed; the other must receive 409 Conflict.
    """
    booking_id = 5001
    req1 = client.post(
        "/api/v1/payments",
        json={"booking_id": booking_id, "user_id": 1, "amount": 2000.0, "currency": "KGS", "provider": "STRIPE"},
    )
    req2 = client.post(
        "/api/v1/payments",
        json={"booking_id": booking_id, "user_id": 2, "amount": 2000.0, "currency": "KGS", "provider": "STRIPE"},
    )

    res1, res2 = await asyncio.gather(req1, req2)
    statuses = [res1.status_code, res2.status_code]

    assert 201 in statuses, "One request must successfully initiate payment"
    assert 409 in statuses, "The concurrent conflicting request must be rejected with 409 Conflict"

@pytest.mark.asyncio
async def test_idempotent_double_click_same_key(client: AsyncClient):
    """
    Scenario: User double-clicks "Pay" or mobile client retries with the same Idempotency-Key.
    Both requests must succeed and return the EXACT same payment object, without duplicating records.
    """
    key = str(uuid.uuid4())
    payload = {"booking_id": 6001, "user_id": 10, "amount": 1500.0, "currency": "KGS", "provider": "STRIPE"}
    headers = {"Idempotency-Key": key}

    req1 = client.post("/api/v1/payments", json=payload, headers=headers)
    req2 = client.post("/api/v1/payments", json=payload, headers=headers)

    res1, res2 = await asyncio.gather(req1, req2)

    assert res1.status_code in (200, 201)
    assert res2.status_code in (200, 201)
    assert res1.json()["id"] == res2.json()["id"], "Both requests must resolve to the identical payment ID"

@pytest.mark.asyncio
async def test_concurrent_pay_confirmation_emits_single_event(client: AsyncClient):
    """
    Scenario: User clicks "Confirm Payment" multiple times simultaneously.
    Payment must succeed, but the RabbitMQ 'payment.succeeded' event must be published exactly once.
    """
    create_res = await client.post(
        "/api/v1/payments",
        json={"booking_id": 7001, "user_id": 33, "amount": 1000.0, "currency": "KGS", "provider": "STRIPE"},
    )
    payment_id = create_res.json()["id"]

    # Clear previous events
    client.published_events.clear()

    # Fire 3 concurrent pay requests
    tasks = [
        client.post(f"/api/v1/payments/{payment_id}/pay", json={"payment_method_id": "pm_card_visa"})
        for _ in range(3)
    ]
    results = await asyncio.gather(*tasks)

    for r in results:
        assert r.status_code == 200
        assert r.json()["status"] == "SUCCEEDED"

    # Exactly one payment.succeeded event emitted
    matching = [e for e in client.published_events if e["payload"]["booking_id"] == 7001]
    assert len(matching) == 1, f"Expected exactly 1 event, got {len(matching)}"

@pytest.mark.asyncio
async def test_duplicate_webhook_delivery_idempotent(client: AsyncClient):
    """
    Scenario: Stripe retries delivery and sends the exact same webhook payload twice concurrently.
    The system must handle both without duplicate events.
    """
    create_res = await client.post(
        "/api/v1/payments",
        json={"booking_id": 8001, "user_id": 44, "amount": 4000.0, "currency": "KGS", "provider": "STRIPE"},
    )
    payment_id = create_res.json()["id"]
    client.published_events.clear()

    webhook_payload = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": create_res.json()["provider_payment_id"],
                "metadata": {"payment_id": str(payment_id)},
            }
        },
    }

    req1 = client.post("/api/v1/payments/webhook", json=webhook_payload)
    req2 = client.post("/api/v1/payments/webhook", json=webhook_payload)

    res1, res2 = await asyncio.gather(req1, req2)
    assert res1.status_code == 200
    assert res2.status_code == 200

    matching = [e for e in client.published_events if e["payload"]["booking_id"] == 8001]
    assert len(matching) == 1, "Duplicate webhook must not emit duplicate events"
