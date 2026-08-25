import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import delete
from sqlalchemy.pool import NullPool
from unittest.mock import patch, AsyncMock
import httpx

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.models.notification import Notification
from app.services import sms_service

# PostgreSQL test connection with NullPool
test_engine = create_async_engine(settings.DATABASE_URL, echo=False, poolclass=NullPool)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture(autouse=True)
async def clean_database():
    async with TestSessionLocal() as session:
        await session.execute(delete(Notification))
        await session.commit()
    yield
    async with TestSessionLocal() as session:
        await session.execute(delete(Notification))
        await session.commit()


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ====================================================================
# 1. BigInteger / Integer Overflow & Boundary Attacks (Fuzzing Limits)
# ====================================================================

@pytest.mark.asyncio
async def test_integer_overflow_user_id_in_create(client: AsyncClient):
    """PostgreSQL BigInteger max is 9223372036854775807. Python ints are unbounded."""
    huge_int = 10**30  # 1000000000000000000000000000000
    res = await client.post("/api/v1/notifications/", json={
        "user_id": huge_int,
        "title": "Overflow User",
        "message": "Testing huge user_id",
        "type": "test"
    })
    # Should be rejected with 422, NOT 500 (DB NumericValueOutOfRangeError)
    assert res.status_code == 422, f"Expected 422 on huge user_id, got {res.status_code}"


@pytest.mark.asyncio
async def test_integer_overflow_related_ids(client: AsyncClient):
    """Related event/booking ID exceeding BigInteger limits."""
    huge_int = 10**30
    res = await client.post("/api/v1/notifications/", json={
        "user_id": 1,
        "title": "Overflow Related",
        "message": "Testing huge related IDs",
        "type": "test",
        "related_event_id": huge_int,
        "related_booking_id": huge_int
    })
    assert res.status_code == 422, f"Expected 422 on huge related_event_id, got {res.status_code}"


@pytest.mark.asyncio
async def test_integer_overflow_query_params(client: AsyncClient):
    """Huge integers in GET /notifications?user_id=... and unread-count."""
    huge_int = 10**30
    res = await client.get(f"/api/v1/notifications/?user_id={huge_int}")
    assert res.status_code == 422, f"Expected 422 on huge user_id query param, got {res.status_code}"

    res2 = await client.get(f"/api/v1/notifications/unread-count?user_id={huge_int}")
    assert res2.status_code == 422, f"Expected 422 on huge user_id in unread-count, got {res2.status_code}"


@pytest.mark.asyncio
async def test_integer_overflow_path_param(client: AsyncClient):
    """Huge integer in PATCH /notifications/{notification_id}/read."""
    huge_int = 10**30
    res = await client.patch(f"/api/v1/notifications/{huge_int}/read")
    assert res.status_code == 422, f"Expected 422 on huge notification_id path param, got {res.status_code}"


@pytest.mark.asyncio
async def test_negative_or_zero_ids(client: AsyncClient):
    """Non-positive IDs (e.g. user_id = 0, user_id = -10)."""
    res_zero = await client.post("/api/v1/notifications/", json={
        "user_id": 0, "title": "Zero", "message": "msg", "type": "info"
    })
    assert res_zero.status_code == 422, "user_id=0 should be rejected with 422"

    res_neg = await client.post("/api/v1/notifications/", json={
        "user_id": -5, "title": "Neg", "message": "msg", "type": "info"
    })
    assert res_neg.status_code == 422, "user_id < 0 should be rejected with 422"


# ====================================================================
# 2. Null Byte & Control Character Injections (Postgres / XML Crashers)
# ====================================================================

@pytest.mark.asyncio
async def test_null_byte_injection_in_title(client: AsyncClient):
    """PostgreSQL rejects strings containing \\x00 (Null Byte) with CharacterNotInRepertoireError."""
    res = await client.post("/api/v1/notifications/", json={
        "user_id": 1,
        "title": "Injected\x00Title",
        "message": "Valid text",
        "type": "info"
    })
    # Must return 422 validation error or sanitize, NOT crash with 500
    assert res.status_code == 422, f"Expected 422 for null byte injection, got {res.status_code}"


@pytest.mark.asyncio
async def test_null_byte_injection_in_message(client: AsyncClient):
    res = await client.post("/api/v1/notifications/", json={
        "user_id": 1,
        "title": "Valid Title",
        "message": "Malicious\x00Message",
        "type": "info"
    })
    assert res.status_code == 422, f"Expected 422 for null byte injection, got {res.status_code}"


# ====================================================================
# 3. SQL Injection Resilience (Verify ORM parameterization)
# ====================================================================

@pytest.mark.asyncio
async def test_sql_injection_in_payload_fields(client: AsyncClient):
    """Ensure SQL injection strings are safely treated as plain text."""
    sqli_payloads = [
        "'; DROP TABLE notifications; --",
        "' OR '1'='1",
        "1; SELECT pg_sleep(2); --",
        "' UNION ALL SELECT 1, 'admin', 'pass', 'hacked', 1, 1, false, NOW() --"
    ]
    for payload in sqli_payloads:
        res = await client.post("/api/v1/notifications/", json={
            "user_id": 1,
            "title": payload[:255],
            "message": payload,
            "type": "sql_test"
        })
        assert res.status_code == 201, f"SQL injection attempt caused unexpected error: {res.status_code}"
        data = res.json()
        assert data["title"] == payload[:255]
        assert data["message"] == payload


# ====================================================================
# 4. SMS Service Aggressive Fuzzing: XML Injection & XXE
# ====================================================================

@pytest.mark.asyncio
async def test_sms_xml_injection_breakout():
    """Attempt to break out of XML tag: </text><phones><phone>996999999999</phone></phones><text>"""
    malicious_text = "</text><login>hacked</login><phone>996999999999</phone><text>"
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.text = "<response><status>0</status></response>"
        mock_post.return_value = mock_response

        success = await sms_service.send_sms_via_nikita("+996555123456", malicious_text)
        assert success is True

        called_kwargs = mock_post.call_args[1]
        xml_content = called_kwargs["content"].decode("utf-8")

        # Must be escaped: &lt;/text&gt;
        assert "&lt;/text&gt;&lt;login&gt;hacked&lt;/login&gt;" in xml_content
        # Ensure raw unescaped tag is NOT present
        assert "</text><login>hacked" not in xml_content


@pytest.mark.asyncio
async def test_sms_xxe_payload():
    """XXE injection test in SMS message."""
    xxe_payload = '<!DOCTYPE test [ <!ENTITY xxe SYSTEM "file:///etc/passwd"> ]><test>&xxe;</test>'
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = lambda: None
        mock_response.text = "<response><status>0</status></response>"
        mock_post.return_value = mock_response

        success = await sms_service.send_sms_via_nikita("+996555123456", xxe_payload)
        assert success is True

        called_kwargs = mock_post.call_args[1]
        xml_content = called_kwargs["content"].decode("utf-8")
        assert "&lt;!DOCTYPE" in xml_content


@pytest.mark.asyncio
async def test_sms_invalid_phone_rejection(client: AsyncClient):
    """Empty or non-digit phone numbers."""
    invalid_phones = ["", "abc", "++++", "()---", " " * 10]
    for bad_phone in invalid_phones:
        res = await client.post("/api/v1/notifications/sms", json={
            "phone_number": bad_phone,
            "message": "Test code"
        })
        # Should be rejected with 422 at schema/router level
        assert res.status_code == 422, f"Bad phone '{bad_phone}' should return 422, got {res.status_code}"


# ====================================================================
# 5. Unicode, Emojis, RTL, Special Characters
# ====================================================================

@pytest.mark.asyncio
async def test_unicode_and_emoji_handling(client: AsyncClient):
    """Test 4-byte UTF-8 emojis, Cyrillic, Arabic RTL, Chinese, special symbols."""
    payload = {
        "user_id": 99,
        "title": "🎉 Акция! Скидка 50% 🚀 🔥",
        "message": "مرحبا بالعالم! 汉语 / 漢語 - 特殊字符: ¡¢£¤¥¦§¨©ª«¬®¯°±²³",
        "type": "unicode_promo"
    }
    res = await client.post("/api/v1/notifications/", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == payload["title"]
    assert data["message"] == payload["message"]


# ====================================================================
# 6. Concurrency & High Load Simulation
# ====================================================================

@pytest.mark.asyncio
async def test_concurrent_notification_creation(client: AsyncClient):
    """Simulate 30 concurrent creation requests for the same user."""
    async def create_one(idx: int):
        return await client.post("/api/v1/notifications/", json={
            "user_id": 555,
            "title": f"Concurrent #{idx}",
            "message": f"Message #{idx}",
            "type": "concurrent"
        })

    tasks = [create_one(i) for i in range(30)]
    responses = await asyncio.gather(*tasks)

    for r in responses:
        assert r.status_code == 201

    # Verify count
    count_res = await client.get("/api/v1/notifications/unread-count?user_id=555")
    assert count_res.json()["unread_count"] == 30

    # Concurrent mark as read
    res_mark = await client.patch("/api/v1/notifications/read-all?user_id=555")
    assert res_mark.status_code == 200
    assert res_mark.json()["updated_count"] == 30
