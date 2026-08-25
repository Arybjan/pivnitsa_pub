import pytest
import asyncio
import time
import httpx
import respx
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import delete
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.models.notification import Notification
from app.services import sms_service

# Test database session
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
# 1. Симуляция сетевых задержек (Network Latency & Jitter)
# ====================================================================

@pytest.mark.asyncio
@respx.mock
async def test_network_latency_simulation():
    """Имитация высокой сетевой задержки (300 мс) при обращении к SMS-шлюзу"""
    async def delayed_response(request):
        await asyncio.sleep(0.3)  # Имитация медленного канала связи
        return httpx.Response(200, text="<response><status>0</status></response>")

    respx.post(settings.NIKITA_API_URL).mock(side_effect=delayed_response)

    start_time = time.perf_counter()
    success = await sms_service.send_sms_via_nikita("+996555123456", "Тест с задержкой")
    elapsed = time.perf_counter() - start_time

    assert success is True
    assert elapsed >= 0.3, f"Задержка должна быть не менее 0.3с, факт: {elapsed:.3f}с"


@pytest.mark.asyncio
@respx.mock
async def test_network_timeout_simulation():
    """Имитация жесткого таймаута сети (сервер шлюза 'завис' и не отвечает)"""
    respx.post(settings.NIKITA_API_URL).mock(side_effect=httpx.ReadTimeout("Read operation timed out"))

    success = await sms_service.send_sms_via_nikita("+996555123456", "Таймаут сообщение")
    assert success is False, "При таймауте метод должен безопасно вернуть False без падения"


# ====================================================================
# 2. Симуляция критических сбоев сети (Network Failures & Disconnects)
# ====================================================================

@pytest.mark.asyncio
@respx.mock
async def test_connection_refused_simulation():
    """Имитация недоступности хоста (Connection Refused / Network Unreachable)"""
    respx.post(settings.NIKITA_API_URL).mock(side_effect=httpx.ConnectError("Connection refused: host unreachable"))

    success = await sms_service.send_sms_via_nikita("+996555123456", "Сообщение при сбое сети")
    assert success is False


@pytest.mark.asyncio
@respx.mock
async def test_remote_disconnect_in_transit():
    """Имитация обрыва соединения посередине передачи данных (Connection Reset By Peer)"""
    respx.post(settings.NIKITA_API_URL).mock(side_effect=httpx.RemoteProtocolError("Connection closed unexpectedly"))

    success = await sms_service.send_sms_via_nikita("+996555123456", "Обрыв связи")
    assert success is False


@pytest.mark.asyncio
@respx.mock
async def test_dns_resolution_failure():
    """Имитация сбоя DNS-сервера (Host not found)"""
    respx.post(settings.NIKITA_API_URL).mock(side_effect=httpx.ConnectError("[Errno -2] Name or service not known"))

    success = await sms_service.send_sms_via_nikita("+996555123456", "DNS ошибка")
    assert success is False


# ====================================================================
# 3. Симуляция серверных ошибок шлюза (HTTP 5xx Outages)
# ====================================================================

@pytest.mark.asyncio
@respx.mock
@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
async def test_gateway_server_outages(status_code: int):
    """Имитация падений внешнего шлюза (500 Internal, 502 Bad Gateway, 503 Unavailable, 504 Timeout)"""
    respx.post(settings.NIKITA_API_URL).mock(return_value=httpx.Response(status_code, text="Server Outage"))

    success = await sms_service.send_sms_via_nikita("+996555123456", f"Тест ошибки {status_code}")
    assert success is False


# ====================================================================
# 4. Нестабильная сеть (Flaky Network Simulation: сбои 1 через 1)
# ====================================================================

@pytest.mark.asyncio
@respx.mock
async def test_flaky_network_simulation():
    """Имитация мерцающей сети: 1-й запрос падает с ConnectError, 2-й успешен, 3-й падает"""
    call_count = 0

    async def flaky_handler(request):
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 1:
            raise httpx.ConnectError("Network packet loss")
        return httpx.Response(200, text="<response><status>0</status></response>")

    respx.post(settings.NIKITA_API_URL).mock(side_effect=flaky_handler)

    # 1-я попытка (сбой)
    res1 = await sms_service.send_sms_via_nikita("+996555111111", "Попытка 1")
    assert res1 is False

    # 2-я попытка (успех)
    res2 = await sms_service.send_sms_via_nikita("+996555111111", "Попытка 2")
    assert res2 is True

    # 3-я попытка (сбой)
    res3 = await sms_service.send_sms_via_nikita("+996555111111", "Попытка 3")
    assert res3 is False


# ====================================================================
# 5. Интеграционный тест: сбои сети в фоновых задачах эндпоинта
# ====================================================================

@pytest.mark.asyncio
@respx.mock
async def test_api_endpoint_resilience_under_network_failure(client: AsyncClient):
    """
    Проверка отказоустойчивости API: когда внешний SMS-шлюз недоступен,
    FastAPI эндпоинт /sms не блокируется и не крашит микросервис.
    """
    respx.post(settings.NIKITA_API_URL).mock(side_effect=httpx.ConnectTimeout("Gateway timed out"))

    # Отправляем запрос на SMS
    res = await client.post("/api/v1/notifications/sms", json={
        "phone_number": "+996555998877",
        "message": "Тест устойчивости"
    })
    assert res.status_code == 200

    # Проверяем, что health check микросервиса продолжает работать штатно
    health = await client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "healthy"}


# ====================================================================
# 6. Конкурентная нагрузка при медленной сети (Slow Network Concurrency)
# ====================================================================

@pytest.mark.asyncio
@respx.mock
async def test_concurrent_requests_under_network_latency():
    """
    Имитация 20 одновременных отправок SMS через медленный канал (200мс на каждый запрос).
    Проверка, что асинхронный event loop не блокируется и запросы выполняются параллельно.
    """
    async def slow_channel(request):
        await asyncio.sleep(0.2)
        return httpx.Response(200, text="<response><status>0</status></response>")

    respx.post(settings.NIKITA_API_URL).mock(side_effect=slow_channel)

    start_time = time.perf_counter()
    tasks = [sms_service.send_sms_via_nikita(f"+9965551122{i:02d}", f"Пакет #{i}") for i in range(20)]
    results = await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_time

    assert all(results)
    # Если бы выполнялись последовательно: 20 * 0.2 = 4.0 секунды.
    # В асинхронном режиме: должно выполниться за ~0.2 - 0.5 секунды.
    assert total_time < 1.0, f"Параллельное выполнение заняло слишком много времени: {total_time:.2f}с"
