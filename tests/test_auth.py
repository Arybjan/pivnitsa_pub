import jwt
import pytest

from app.core.config import settings
from tests.conftest import PASSWORD, auth_header, get_verification_token, register_user

PHONE = "+996555123456"


async def test_health_reports_dependencies(client):
    response = await client.get("/health")
    assert response.json()["service"] == "auth"


# --- Регистрация ---

async def test_register_full_flow(client):
    body = await register_user(client, first_name="Азамат", email="aza@example.com")
    assert body["token_type"] == "bearer"
    assert body["user"]["phone"] == PHONE
    assert body["user"]["first_name"] == "Азамат"
    assert body["user"]["role"] == "user"
    assert isinstance(body["user"]["id"], int)


@pytest.mark.parametrize(
    "raw",
    ["0555 12-34-56", "0555123456", "+0555123456", "555123456", "996555123456", "+996 (555) 123 456", "00996555123456"],
)
async def test_phone_is_normalized(client, raw):
    sent = await client.post("/api/v1/auth/otp/send", json={"phone": raw})
    code = sent.json()["debug_code"]
    verified = await client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": code})
    assert verified.status_code == 200


@pytest.mark.parametrize("raw", ["12345abc", "0555abc123456", "+012345678901", "12345"])
async def test_invalid_phone_rejected(client, raw):
    response = await client.post("/api/v1/auth/otp/send", json={"phone": raw})
    assert response.status_code == 422


async def test_register_twice_conflicts(client):
    await register_user(client)
    response = await client.post("/api/v1/auth/otp/send", json={"phone": PHONE, "purpose": "register"})
    assert response.status_code == 409


async def test_verification_token_is_single_use(client):
    token = await get_verification_token(client, PHONE)
    first = await client.post("/api/v1/auth/register", json={"verification_token": token, "password": PASSWORD})
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json={"verification_token": token, "password": PASSWORD})
    assert second.status_code == 401


async def test_verification_token_purpose_is_enforced(client):
    await register_user(client)
    login_token = await get_verification_token(client, "+996700000001", purpose="login")
    response = await client.post("/api/v1/auth/register", json={"verification_token": login_token, "password": PASSWORD})
    assert response.status_code == 401


@pytest.mark.parametrize("password", ["short1", "onlyletters", "12345678", "a1" * 40])
async def test_weak_password_rejected(client, password):
    token = await get_verification_token(client, PHONE)
    response = await client.post("/api/v1/auth/register", json={"verification_token": token, "password": password})
    assert response.status_code == 422


async def test_duplicate_email_conflicts(client):
    await register_user(client, email="same@example.com")
    token = await get_verification_token(client, "+996700000002")
    response = await client.post(
        "/api/v1/auth/register", json={"verification_token": token, "password": PASSWORD, "email": "same@example.com"}
    )
    assert response.status_code == 409


# --- OTP ---

async def test_wrong_code_and_attempt_limit(client):
    sent = await client.post("/api/v1/auth/otp/send", json={"phone": PHONE})
    code = sent.json()["debug_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(settings.OTP_MAX_ATTEMPTS - 1):
        response = await client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": wrong})
        assert response.status_code == 400
    response = await client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": wrong})
    assert response.status_code == 429
    # После превышения лимита даже верный код не принимается
    response = await client.post("/api/v1/auth/otp/verify", json={"phone": PHONE, "code": code})
    assert response.status_code == 400


async def test_resend_cooldown(client):
    assert (await client.post("/api/v1/auth/otp/send", json={"phone": PHONE})).status_code == 200
    response = await client.post("/api/v1/auth/otp/send", json={"phone": PHONE})
    assert response.status_code == 429
    assert int(response.headers["Retry-After"]) > 0


async def test_retry_after_visible_to_browser(client):
    origin = {"Origin": "http://localhost:3000"}
    await client.post("/api/v1/auth/otp/send", json={"phone": PHONE}, headers=origin)
    response = await client.post("/api/v1/auth/otp/send", json={"phone": PHONE}, headers=origin)
    assert response.status_code == 429
    assert "retry-after" in response.headers["Access-Control-Expose-Headers"].lower()


async def test_hourly_send_limit(client, redis):
    for i in range(settings.OTP_MAX_SENDS_PER_HOUR):
        await redis.delete(f"auth:otp_cooldown:register:{PHONE}")
        assert (await client.post("/api/v1/auth/otp/send", json={"phone": PHONE})).status_code == 200
    await redis.delete(f"auth:otp_cooldown:register:{PHONE}")
    assert (await client.post("/api/v1/auth/otp/send", json={"phone": PHONE})).status_code == 429


async def test_code_is_not_stored_in_plain_text(client, redis):
    sent = await client.post("/api/v1/auth/otp/send", json={"phone": PHONE})
    stored = await redis.hgetall(f"auth:otp:register:{PHONE}")
    assert sent.json()["debug_code"] not in str(stored)


async def test_login_otp_for_unknown_phone_looks_the_same(client):
    response = await client.post("/api/v1/auth/otp/send", json={"phone": "+996700999999", "purpose": "login"})
    assert response.status_code == 200


async def test_debug_code_hidden_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    response = await client.post("/api/v1/auth/otp/send", json={"phone": PHONE})
    assert response.json()["debug_code"] is None


# --- Вход ---

async def test_login_with_password(client):
    await register_user(client)
    response = await client.post("/api/v1/auth/login", json={"phone": "0555123456", "password": PASSWORD})
    assert response.status_code == 200
    assert response.json()["user"]["phone"] == PHONE


async def test_login_with_otp(client):
    await register_user(client)
    token = await get_verification_token(client, PHONE, purpose="login")
    response = await client.post("/api/v1/auth/login", json={"verification_token": token})
    assert response.status_code == 200


async def test_login_wrong_password_and_unknown_phone_same_error(client):
    await register_user(client)
    wrong = await client.post("/api/v1/auth/login", json={"phone": PHONE, "password": "wrong1234"})
    unknown = await client.post("/api/v1/auth/login", json={"phone": "+996700111222", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


async def test_login_lockout_after_failures(client):
    await register_user(client)
    for _ in range(settings.LOGIN_MAX_FAILED_ATTEMPTS):
        await client.post("/api/v1/auth/login", json={"phone": PHONE, "password": "wrong1234"})
    response = await client.post("/api/v1/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert response.status_code == 429


async def test_login_requires_exactly_one_method(client):
    response = await client.post("/api/v1/auth/login", json={"phone": PHONE})
    assert response.status_code == 422


# --- Токены: контракт с другими сервисами ---

async def test_access_token_matches_team_contract(client):
    body = await register_user(client)
    payload = jwt.decode(body["access_token"], settings.JWT_SECRET, algorithms=["HS256"])
    assert int(payload["sub"]) == body["user"]["id"]  # Booking / Payment: int(payload["sub"])
    assert payload["role"] == "user"
    assert payload["phone"] == PHONE
    assert payload["is_active"] is True  # Event / Notification
    assert payload["type"] == payload["token_type"] == "access"


async def test_refresh_token_not_accepted_by_other_services(client):
    body = await register_user(client)
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(body["refresh_token"], settings.JWT_SECRET, algorithms=["HS256"])


async def test_refresh_rotation_and_reuse_detection(client):
    body = await register_user(client)
    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]

    # Повторное использование старого токена отзывает все сессии, включая новую
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert reuse.status_code == 401
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401


async def test_access_token_cannot_be_used_as_refresh(client):
    body = await register_user(client)
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": body["access_token"]})
    assert response.status_code == 401


async def test_logout_revokes_refresh(client):
    body = await register_user(client)
    assert (await client.post("/api/v1/auth/logout", json={"refresh_token": body["refresh_token"]})).status_code == 204
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert response.status_code == 401


async def test_logout_all(client):
    body = await register_user(client)
    second = (await client.post("/api/v1/auth/login", json={"phone": PHONE, "password": PASSWORD})).json()
    assert (await client.post("/api/v1/auth/logout-all", headers=auth_header(body["access_token"]))).status_code == 204
    for token in (body["refresh_token"], second["refresh_token"]):
        assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": token})).status_code == 401


# --- Сброс пароля ---

async def test_password_reset(client):
    body = await register_user(client)
    token = await get_verification_token(client, PHONE, purpose="reset_password")
    response = await client.post(
        "/api/v1/auth/password/reset", json={"verification_token": token, "new_password": "newpass456"}
    )
    assert response.status_code == 204
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})).status_code == 401
    old = await client.post("/api/v1/auth/login", json={"phone": PHONE, "password": PASSWORD})
    new = await client.post("/api/v1/auth/login", json={"phone": PHONE, "password": "newpass456"})
    assert old.status_code == 401
    assert new.status_code == 200
