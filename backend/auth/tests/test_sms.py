import httpx
import jwt
import respx

from app.core.config import settings


async def test_sms_sent_through_notification_service(client, monkeypatch):
    monkeypatch.setattr(settings, "SMS_PROVIDER", "notification")
    with respx.mock(base_url=settings.NOTIFICATION_SERVICE_URL) as mock:
        route = mock.post("/api/v1/notifications/sms").respond(200, json={"status": "success", "message": "queued"})
        response = await client.post("/api/v1/auth/otp/send", json={"phone": "+996555123456"})

    assert response.status_code == 200
    request = route.calls.last.request
    body = request.read().decode()
    assert "+996555123456" in body and response.json()["debug_code"] in body
    token = request.headers["Authorization"].removeprefix("Bearer ")
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    assert payload["role"] == "service" and payload["token_type"] == "access"
    assert int(payload["sub"]) > 0


async def test_sms_failure_returns_503_and_allows_retry(client, monkeypatch):
    monkeypatch.setattr(settings, "SMS_PROVIDER", "notification")
    with respx.mock(base_url=settings.NOTIFICATION_SERVICE_URL) as mock:
        mock.post("/api/v1/notifications/sms").mock(side_effect=httpx.ConnectError("down"))
        failed = await client.post("/api/v1/auth/otp/send", json={"phone": "+996555123456"})
        assert failed.status_code == 503
        mock.post("/api/v1/notifications/sms").respond(200, json={})
        retry = await client.post("/api/v1/auth/otp/send", json={"phone": "+996555123456"})
        assert retry.status_code == 200
