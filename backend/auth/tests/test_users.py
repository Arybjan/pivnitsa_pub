from tests.conftest import PASSWORD, auth_header, register_user

PHONE = "+996555123456"


async def _make_role(session_maker, user_id: int, role: str):
    from app.models import User

    async with session_maker() as db:
        user = await db.get(User, user_id)
        user.role = role
        await db.commit()


async def _login(client, phone=PHONE, password=PASSWORD) -> dict:
    response = await client.post("/api/v1/auth/login", json={"phone": phone, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


async def test_me_requires_token(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    assert (await client.get("/api/v1/users/me", headers=auth_header("garbage"))).status_code == 401


async def test_get_and_update_me(client):
    body = await register_user(client)
    headers = auth_header(body["access_token"])
    me = await client.get("/api/v1/users/me", headers=headers)
    assert me.json()["phone"] == PHONE

    response = await client.patch(
        "/api/v1/users/me",
        headers=headers,
        json={"first_name": "Арыбжан", "last_name": "Азизов", "email": "a@example.com", "avatar_url": "https://cdn.example.com/a.png"},
    )
    assert response.status_code == 200
    data = response.json()
    assert (data["first_name"], data["last_name"], data["email"]) == ("Арыбжан", "Азизов", "a@example.com")

    # Частичное обновление не трогает остальные поля
    response = await client.patch("/api/v1/users/me", headers=headers, json={"last_name": None})
    assert response.json()["first_name"] == "Арыбжан"
    assert response.json()["last_name"] is None


async def test_update_me_rejects_unknown_and_protected_fields(client):
    body = await register_user(client)
    response = await client.patch("/api/v1/users/me", headers=auth_header(body["access_token"]), json={"role": "owner"})
    assert response.status_code == 422


async def test_update_email_conflict(client):
    await register_user(client, email="taken@example.com")
    other = await register_user(client, phone="+996700000003")
    response = await client.patch(
        "/api/v1/users/me", headers=auth_header(other["access_token"]), json={"email": "taken@example.com"}
    )
    assert response.status_code == 409


async def test_change_password(client):
    body = await register_user(client)
    headers = auth_header(body["access_token"])
    wrong = await client.post("/api/v1/users/me/password", headers=headers, json={"current_password": "nope12345", "new_password": "fresh1234"})
    assert wrong.status_code == 400
    ok = await client.post("/api/v1/users/me/password", headers=headers, json={"current_password": PASSWORD, "new_password": "fresh1234"})
    assert ok.status_code == 204
    await _login(client, password="fresh1234")


async def test_delete_me_deactivates_account(client):
    body = await register_user(client)
    headers = auth_header(body["access_token"])
    assert (await client.delete("/api/v1/users/me", headers=headers)).status_code == 204
    # Старый access-токен сразу перестаёт работать в Auth Service
    assert (await client.get("/api/v1/users/me", headers=headers)).status_code == 401
    login = await client.post("/api/v1/auth/login", json={"phone": PHONE, "password": PASSWORD})
    assert login.status_code == 403
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})).status_code == 401


async def test_admin_endpoints_forbidden_for_user(client):
    body = await register_user(client)
    headers = auth_header(body["access_token"])
    assert (await client.get("/api/v1/users", headers=headers)).status_code == 403
    assert (await client.get(f"/api/v1/users/{body['user']['id']}", headers=headers)).status_code == 403


async def test_admin_can_list_and_block_users(client, session_maker):
    admin = await register_user(client)
    user = await register_user(client, phone="+996700000004")
    await _make_role(session_maker, admin["user"]["id"], "admin")
    headers = auth_header(admin["access_token"])

    listing = await client.get("/api/v1/users", headers=headers, params={"role": "user"})
    assert listing.status_code == 200
    assert listing.json()["total"] == 1

    blocked = await client.patch(f"/api/v1/users/{user['user']['id']}", headers=headers, json={"is_active": False})
    assert blocked.status_code == 200
    assert blocked.json()["is_active"] is False
    assert (await client.post("/api/v1/auth/refresh", json={"refresh_token": user["refresh_token"]})).status_code == 401


async def test_admin_cannot_change_roles(client, session_maker):
    admin = await register_user(client)
    user = await register_user(client, phone="+996700000005")
    await _make_role(session_maker, admin["user"]["id"], "admin")
    response = await client.patch(
        f"/api/v1/users/{user['user']['id']}", headers=auth_header(admin["access_token"]), json={"role": "admin"}
    )
    assert response.status_code == 403


async def test_owner_can_promote_and_token_reflects_role(client, session_maker):
    owner = await register_user(client)
    user = await register_user(client, phone="+996700000006")
    await _make_role(session_maker, owner["user"]["id"], "owner")
    response = await client.patch(
        f"/api/v1/users/{user['user']['id']}", headers=auth_header(owner["access_token"]), json={"role": "admin"}
    )
    assert response.status_code == 200
    relogin = await _login(client, phone="+996700000006")
    assert relogin["user"]["role"] == "admin"


async def test_cannot_modify_self_via_admin_endpoint(client, session_maker):
    owner = await register_user(client)
    await _make_role(session_maker, owner["user"]["id"], "owner")
    response = await client.patch(
        f"/api/v1/users/{owner['user']['id']}", headers=auth_header(owner["access_token"]), json={"is_active": False}
    )
    assert response.status_code == 400


async def test_get_unknown_user_404(client, session_maker):
    admin = await register_user(client)
    await _make_role(session_maker, admin["user"]["id"], "admin")
    response = await client.get("/api/v1/users/999999", headers=auth_header(admin["access_token"]))
    assert response.status_code == 404
