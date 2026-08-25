import pytest
from typing import AsyncGenerator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import delete
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.config import settings
from app.core.database import get_db
from app.models.notification import Notification

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
# 1. Тестирование информативности ошибок валидации полей (422)
# ====================================================================

@pytest.mark.asyncio
async def test_error_missing_body_fields(client: AsyncClient):
    """Проверка информативности ошибки при отсутствии обязательных полей в теле"""
    res = await client.post("/api/v1/notifications/", json={})
    assert res.status_code == 422
    data = res.json()
    assert "detail" in data
    # Должны быть четко указаны все 4 отсутствующих поля
    missing_fields = {tuple(err["loc"]) for err in data["detail"]}
    assert ("body", "user_id") in missing_fields
    assert ("body", "title") in missing_fields
    assert ("body", "message") in missing_fields
    assert ("body", "type") in missing_fields
    for err in data["detail"]:
        assert err["type"] == "missing"
        assert "Field required" in err["msg"]


@pytest.mark.asyncio
async def test_error_type_mismatch_in_body(client: AsyncClient):
    """Проверка ошибки при передаче неверных типов данных (строка вместо int)"""
    res = await client.post("/api/v1/notifications/", json={
        "user_id": "not_a_number",
        "title": 12345,  # int can be coerced or validated
        "message": "Valid message",
        "type": "booking"
    })
    assert res.status_code == 422
    data = res.json()
    err = next(e for e in data["detail"] if "user_id" in e["loc"])
    assert "int" in err["msg"].lower() or "integer" in err["msg"].lower()


@pytest.mark.asyncio
async def test_error_empty_string_validation(client: AsyncClient):
    """Проверка ошибки при передаче пустых строк (min_length=1)"""
    res = await client.post("/api/v1/notifications/", json={
        "user_id": 1,
        "title": "",
        "message": "",
        "type": ""
    })
    assert res.status_code == 422
    data = res.json()
    for err in data["detail"]:
        assert "at least 1 character" in err["msg"] or "min_length" in err["type"]


@pytest.mark.asyncio
async def test_error_max_length_exceeded(client: AsyncClient):
    """Проверка информативности ошибки при превышении max_length"""
    res = await client.post("/api/v1/notifications/", json={
        "user_id": 1,
        "title": "A" * 256,
        "message": "Valid message",
        "type": "T" * 31
    })
    assert res.status_code == 422
    data = res.json()
    err_title = next(e for e in data["detail"] if "title" in e["loc"])
    assert "at most 255 characters" in err_title["msg"] or "max_length" in err_title["type"]

    err_type = next(e for e in data["detail"] if "type" in e["loc"])
    assert "at most 30 characters" in err_type["msg"] or "max_length" in err_type["type"]


@pytest.mark.asyncio
async def test_error_numeric_bounds(client: AsyncClient):
    """Проверка информативности ошибок выхода за числовые границы (gt=0, le=MAX_BIGINT)"""
    res_zero = await client.post("/api/v1/notifications/", json={
        "user_id": 0, "title": "t", "message": "m", "type": "info"
    })
    assert res_zero.status_code == 422
    assert "greater than 0" in res_zero.json()["detail"][0]["msg"]

    res_overflow = await client.post("/api/v1/notifications/", json={
        "user_id": 10**25, "title": "t", "message": "m", "type": "info"
    })
    assert res_overflow.status_code == 422
    assert "less than or equal to 9223372036854775807" in res_overflow.json()["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_error_null_byte_rejection(client: AsyncClient):
    """Проверка информативности кастомной ошибки на Null-byte"""
    res = await client.post("/api/v1/notifications/", json={
        "user_id": 1,
        "title": "Bad\x00Title",
        "message": "msg",
        "type": "info"
    })
    assert res.status_code == 422
    err_msg = res.json()["detail"][0]["msg"]
    assert "Null bytes (\\x00) are not allowed" in err_msg


# ====================================================================
# 2. Тестирование ошибок в Query и Path параметрах
# ====================================================================

@pytest.mark.asyncio
async def test_error_missing_query_parameter(client: AsyncClient):
    """Проверка ошибки при отсутствии обязательного query-параметра user_id"""
    res = await client.get("/api/v1/notifications/")
    assert res.status_code == 422
    data = res.json()
    err = data["detail"][0]
    assert err["loc"] == ["query", "user_id"]
    assert err["type"] == "missing"
    assert "Field required" in err["msg"]


@pytest.mark.asyncio
async def test_error_invalid_query_parameter_type(client: AsyncClient):
    """Проверка ошибки при нечисловом user_id в GET запросе"""
    res = await client.get("/api/v1/notifications/?user_id=invalid_id")
    assert res.status_code == 422
    data = res.json()
    err = data["detail"][0]
    assert err["loc"] == ["query", "user_id"]
    assert "int" in err["msg"].lower() or "integer" in err["msg"].lower()


@pytest.mark.asyncio
async def test_error_invalid_pagination_query_parameters(client: AsyncClient):
    """Проверка ошибок диапазона limit и offset"""
    # limit = 0 (меньше минимума 1)
    res_lim0 = await client.get("/api/v1/notifications/?user_id=1&limit=0")
    assert res_lim0.status_code == 422
    assert "greater than or equal to 1" in res_lim0.json()["detail"][0]["msg"]

    # limit = 500 (больше максимума 100)
    res_lim500 = await client.get("/api/v1/notifications/?user_id=1&limit=500")
    assert res_lim500.status_code == 422
    assert "less than or equal to 100" in res_lim500.json()["detail"][0]["msg"]

    # offset = -10 (отрицательный)
    res_off = await client.get("/api/v1/notifications/?user_id=1&offset=-10")
    assert res_off.status_code == 422
    assert "greater than or equal to 0" in res_off.json()["detail"][0]["msg"]


@pytest.mark.asyncio
async def test_error_invalid_path_parameter_type(client: AsyncClient):
    """Проверка ошибки при нечисловом ID в пути /{notification_id}/read"""
    res = await client.patch("/api/v1/notifications/abc/read")
    assert res.status_code == 422
    data = res.json()
    err = data["detail"][0]
    assert err["loc"] == ["path", "notification_id"]
    assert "int" in err["msg"].lower() or "integer" in err["msg"].lower()


# ====================================================================
# 3. Тестирование ошибок в SMS-эндпоинте
# ====================================================================

@pytest.mark.asyncio
async def test_error_sms_short_phone(client: AsyncClient):
    """Проверка ошибки при слишком коротком или нецифровом номере телефона"""
    res = await client.post("/api/v1/notifications/sms", json={
        "phone_number": "12",
        "message": "Hello"
    })
    assert res.status_code == 422
    err_msg = str(res.json()["detail"])
    assert "Phone number must contain at least 5 digits" in err_msg or "at least 5 characters" in err_msg


@pytest.mark.asyncio
async def test_error_sms_missing_message(client: AsyncClient):
    res = await client.post("/api/v1/notifications/sms", json={
        "phone_number": "+996555123456"
    })
    assert res.status_code == 422
    assert ("body", "message") in [tuple(e["loc"]) for e in res.json()["detail"]]


# ====================================================================
# 4. Тестирование ошибок 404 (Resource Not Found)
# ====================================================================

@pytest.mark.asyncio
async def test_error_notification_not_found(client: AsyncClient):
    """Проверка понятного сообщения при обновлении несуществующего уведомления"""
    res = await client.patch("/api/v1/notifications/99999999/read")
    assert res.status_code == 404
    assert res.json() == {"detail": "Notification not found"}


@pytest.mark.asyncio
async def test_error_unknown_endpoint_404(client: AsyncClient):
    """Проверка 404 для несуществующих путей"""
    res = await client.get("/api/v1/notifications/some_random_route")
    assert res.status_code == 404
    assert res.json() == {"detail": "Not Found"}


# ====================================================================
# 5. Тестирование ошибок 405 (Method Not Allowed)
# ====================================================================

@pytest.mark.asyncio
async def test_error_method_not_allowed(client: AsyncClient):
    """Проверка 405 при использовании неподдерживаемых HTTP-методов"""
    # DELETE на /api/v1/notifications/
    res_del = await client.delete("/api/v1/notifications/")
    assert res_del.status_code == 405
    assert res_del.json() == {"detail": "Method Not Allowed"}

    # PUT на /api/v1/notifications/
    res_put = await client.put("/api/v1/notifications/")
    assert res_put.status_code == 405
    assert res_put.json() == {"detail": "Method Not Allowed"}


# ====================================================================
# 6. Тестирование некорректного JSON синтаксиса
# ====================================================================

@pytest.mark.asyncio
async def test_error_malformed_json_syntax(client: AsyncClient):
    """Проверка ошибки 422 при битом JSON"""
    res = await client.post(
        "/api/v1/notifications/",
        content='{"title": "Broken JSON',
        headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 422
    assert "JSON decode error" in res.json()["detail"][0]["msg"] or "json_invalid" in res.json()["detail"][0]["type"]
