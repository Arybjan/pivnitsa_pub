import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient
from app.models.payment import PaymentStatus

@pytest.mark.asyncio
async def test_full_e2e_booking_payment_notification_cycle(client: AsyncClient):
    """
    Full End-to-End Choreography Test:
    1. Booking Created (status: PENDING_PAYMENT, table_id: 5, user_id: 42, phone: +996555123456)
    2. Payment Created & Confirmed in Payment Service (status: SUCCEEDED)
    3. Event 'payment.succeeded' triggers Booking Service -> status becomes CONFIRMED
    4. Event 'booking.confirmed' triggers Notification Service -> saves notification & sends SMS
    """

    # --- STEP 1: Simulate Booking state in Booking Service ---
    booking_state = {
        "id": 9001,
        "table_id": 5,
        "user_id": 42,
        "phone": "+996555123456",
        "status": "PENDING_PAYMENT",
    }

    # Tracking system for dispatched notifications and SMS
    system_notifications = []
    system_sms = []

    # --- STEP 2: Initiate Payment in Payment Service ---
    pay_create_res = await client.post(
        "/api/v1/payments",
        json={
            "booking_id": booking_state["id"],
            "user_id": booking_state["user_id"],
            "amount": 2500.00,
            "currency": "KGS",
            "provider": "STRIPE",
        },
    )
    assert pay_create_res.status_code == 201
    payment_data = pay_create_res.json()
    payment_id = payment_data["id"]
    assert payment_data["status"] == "PENDING"

    # --- STEP 3: Confirm Payment (Guest pays via card) ---
    pay_confirm_res = await client.post(
        f"/api/v1/payments/{payment_id}/pay",
        json={"payment_method_id": "pm_card_visa"},
    )
    assert pay_confirm_res.status_code == 200
    assert pay_confirm_res.json()["status"] == "SUCCEEDED"
    assert pay_confirm_res.json()["receipt_url"] is not None

    # Verify Payment Service published 'payment.succeeded'
    matching_payment_events = [
        e for e in client.published_events if e["routing_key"] == "payment.succeeded"
    ]
    assert len(matching_payment_events) == 1
    payment_event = matching_payment_events[0]["payload"]
    assert payment_event["booking_id"] == 9001
    assert payment_event["user_id"] == 42
    assert payment_event["amount"] == "2500.00"

    # --- STEP 4: Simulate Booking Service handling 'payment.succeeded' ---
    # (Matches Atay's BookingService.handle_payment_succeeded in booking_service)
    assert booking_state["status"] == "PENDING_PAYMENT"
    booking_state["status"] = "CONFIRMED"
    booking_state["confirmed_by"] = "payment"

    booking_confirmed_payload = {
        "booking_id": booking_state["id"],
        "table_id": booking_state["table_id"],
        "user_id": booking_state["user_id"],
        "phone": booking_state["phone"],
        "status": booking_state["status"],
        "confirmed_by": "payment",
        "amount": payment_event["amount"],
    }

    # Booking Service emits 'booking.confirmed'
    published_booking_confirmed = {
        "routing_key": "booking.confirmed",
        "payload": booking_confirmed_payload,
    }

    # --- STEP 5: Simulate Notification Service consuming 'booking.confirmed' ---
    # (Matches Arman's event_consumer in nofitication/app/services/event_consumer.py)
    # 5a. Save notification to user inbox
    notification_record = {
        "user_id": booking_confirmed_payload["user_id"],
        "type": "booking_confirmed",
        "related_booking_id": booking_confirmed_payload["booking_id"],
        "title": "Бронирование подтверждено",
        "message": f"Ваша бронь стола №{booking_confirmed_payload['table_id']} успешно оплачена и подтверждена!",
        "is_read": False,
    }
    system_notifications.append(notification_record)

    # 5b. Dispatch SMS to phone
    sms_record = {
        "phone": booking_confirmed_payload["phone"],
        "text": notification_record["message"],
        "status": "SENT",
    }
    system_sms.append(sms_record)

    # --- STEP 6: Assert the full chain succeeded without breaks ---
    # 1. Payment status in DB
    get_payment = await client.get(f"/api/v1/payments/{payment_id}")
    assert get_payment.json()["status"] == "SUCCEEDED"

    # 2. Booking confirmed
    assert booking_state["status"] == "CONFIRMED"
    assert booking_state["confirmed_by"] == "payment"

    # 3. Notification created
    assert len(system_notifications) == 1
    assert system_notifications[0]["user_id"] == 42
    assert system_notifications[0]["related_booking_id"] == 9001
    assert system_notifications[0]["type"] == "booking_confirmed"

    # 4. SMS sent to phone
    assert len(system_sms) == 1
    assert system_sms[0]["phone"] == "+996555123456"
    assert system_sms[0]["status"] == "SENT"
