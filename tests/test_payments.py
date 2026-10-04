import json
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from app.models.payment import Payment, PaymentStatus
from app.messaging.consumer import consumer

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "payment-service"

@pytest.mark.asyncio
async def test_create_payment_and_pay_flow(client: AsyncClient):
    # 1. Initiate Payment for booking #101
    payload = {
        "booking_id": 101,
        "user_id": 42,
        "amount": 2500.00,
        "currency": "KGS",
        "provider": "STRIPE",
    }
    create_res = await client.post("/api/v1/payments", json=payload)
    assert create_res.status_code == 201
    payment = create_res.json()
    payment_id = payment["id"]

    assert payment["booking_id"] == 101
    assert payment["user_id"] == 42
    assert float(payment["amount"]) == 2500.00
    assert payment["currency"] == "KGS"
    assert payment["status"] == "PENDING"
    assert payment["provider_payment_id"] is not None
    assert payment["checkout_url"] == f"/api/v1/payments/{payment_id}/checkout"

    # 2. Check Payment Status
    get_res = await client.get(f"/api/v1/payments/{payment_id}")
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "PENDING"

    # 3. Render HTML Checkout
    checkout_html_res = await client.get(f"/api/v1/payments/{payment_id}/checkout")
    assert checkout_html_res.status_code == 200
    assert "Pivnitsa Pub" in checkout_html_res.text

    # 4. Confirm Payment (Simulated / Live Card Checkout)
    pay_res = await client.post(f"/api/v1/payments/{payment_id}/pay", json={"payment_method_id": "pm_card_visa"})
    assert pay_res.status_code == 200
    paid_data = pay_res.json()
    assert paid_data["status"] == "SUCCEEDED"
    assert paid_data["receipt_url"] is not None

    # Verify RabbitMQ event published for Atay's booking service
    assert len(client.published_events) == 1
    event = client.published_events[0]
    assert event["routing_key"] == "payment.succeeded"
    assert event["payload"]["booking_id"] == 101
    assert event["payload"]["user_id"] == 42
    assert event["payload"]["amount"] == "2500.00"

    # 5. Duplicate Payment Prevention: Trying to initiate another payment for same booking must fail
    dup_res = await client.post("/api/v1/payments", json=payload)
    assert dup_res.status_code == 409

    # 6. Refund Payment
    refund_res = await client.post(f"/api/v1/payments/{payment_id}/refund", json={"reason": "customer_cancellation"})
    assert refund_res.status_code == 200
    assert refund_res.json()["status"] == "REFUNDED"

@pytest.mark.asyncio
async def test_webhook_payment_confirmation(client: AsyncClient):
    payload = {
        "booking_id": 202,
        "user_id": 88,
        "amount": 1500.00,
        "currency": "KGS",
        "provider": "STRIPE",
    }
    create_res = await client.post("/api/v1/payments", json=payload)
    payment_id = create_res.json()["id"]

    webhook_data = {
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": create_res.json()["provider_payment_id"],
                "metadata": {"payment_id": str(payment_id)},
                "charges": {"data": [{"receipt_url": "https://stripe.com/receipts/test_123"}]},
            }
        },
    }
    wh_res = await client.post("/api/v1/payments/webhook", json=webhook_data)
    assert wh_res.status_code == 200
    assert wh_res.json()["status"] == "confirmed"

    get_res = await client.get(f"/api/v1/payments/{payment_id}")
    assert get_res.json()["status"] == "SUCCEEDED"
    assert get_res.json()["receipt_url"] == "https://stripe.com/receipts/test_123"

    matching_events = [e for e in client.published_events if e["payload"]["booking_id"] == 202]
    assert len(matching_events) == 1
    assert matching_events[0]["routing_key"] == "payment.succeeded"

@pytest.mark.asyncio
async def test_payment_not_found(client: AsyncClient):
    res = await client.get("/api/v1/payments/999999")
    assert res.status_code == 404

@pytest.mark.asyncio
async def test_refund_pending_payment_fails(client: AsyncClient):
    payload = {
        "booking_id": 303,
        "user_id": 55,
        "amount": 1000.00,
        "currency": "KGS",
        "provider": "STRIPE",
    }
    create_res = await client.post("/api/v1/payments", json=payload)
    payment_id = create_res.json()["id"]

    # Refunding a PENDING payment should fail (must be SUCCEEDED first)
    res = await client.post(f"/api/v1/payments/{payment_id}/refund")
    assert res.status_code == 400
    assert "Only SUCCEEDED payments can be refunded" in res.json()["detail"]
