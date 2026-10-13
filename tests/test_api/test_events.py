from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, func
from app.models.events import EventOutbox
from app.services.outbox import deliver_pending
from tests.conftest import USER_ID

pytestmark = pytest.mark.asyncio


async def test_create_and_draft_visibility(client, token, event_data):
    created = await client.post("/api/v1/events", headers=token(), json=event_data)
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["created_by"] == USER_ID
    assert event["status"] == "DRAFT"
    assert "starts_at" in event and "ends_at" in event
    path = f'/api/v1/events/{event["id"]}'
    assert (await client.get(path)).status_code == 404
    assert (await client.get(path, headers=token(role="guest"))).status_code == 404
    assert (await client.get(path, headers=token())).status_code == 200
    assert (await client.get("/api/v1/events")).json()["total"] == 0


@pytest.mark.parametrize("claims,code", [
    ({"type": "refresh"}, 401), ({"is_active": False}, 403),
    ({"sub": "invalid"}, 401), ({"exp": 1}, 401),
    ({"role": "guest"}, 403), ({"type": None}, 401),
    ({"is_active": "false"}, 403), ({"token_type": "refresh"}, 401),
])
async def test_invalid_and_unauthorized_tokens(client, token, event_data, claims, code):
    response = await client.post("/api/v1/events", headers=token(**claims), json=event_data)
    assert response.status_code == code, response.text


async def test_missing_token(client, event_data):
    assert (await client.post("/api/v1/events", json=event_data)).status_code == 401


async def test_all_route_and_total(client, token, event_data):
    for _ in range(2):
        assert (await client.post("/api/v1/events", headers=token(), json=event_data)).status_code == 201
    response = await client.get("/api/v1/events/all?limit=1", headers=token())
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 2
    assert response.json()["has_next"] is True
    assert (await client.get("/api/v1/events/all", headers=token(role="guest"))).status_code == 403
    assert (await client.get("/api/v1/events/all?status=garbage", headers=token())).status_code == 422


async def test_publish_unpublish_patch_and_finished(client, token, event_data, sessions):
    event_id = (await client.post("/api/v1/events", headers=token(), json=event_data)).json()["id"]
    path = f"/api/v1/events/{event_id}"
    assert (await client.patch(path, headers=token(), json={"title": "Updated"})).json()["title"] == "Updated"
    for _ in range(2):
        response = await client.post(path + "/publish", headers=token())
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "PUBLISHED"
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(EventOutbox)) == 1
    assert (await client.get(path)).status_code == 200
    assert (await client.get("/api/v1/events")).json()["total"] == 1
    assert (await client.post(path + "/unpublish", headers=token())).json()["status"] == "DRAFT"
    assert (await client.get(path)).status_code == 404
    assert (await client.post(path + "/publish", headers=token(), json={"send_notifications": False})).status_code == 200
    assert (await client.patch(path, headers=token(), json={"status": "FINISHED"})).json()["status"] == "FINISHED"
    assert (await client.post(path + "/publish", headers=token())).status_code == 409
    assert (await client.post(path + "/cancel", headers=token())).status_code == 409


async def test_cannot_bypass_publish_or_break_non_nullable_fields(client, token, event_data):
    event_id = (await client.post("/api/v1/events", headers=token(), json=event_data)).json()["id"]
    for update in ({"status": "PUBLISHED"}, {"status": None}, {"title": None}, {"starts_at": None}):
        assert (await client.patch(f"/api/v1/events/{event_id}", headers=token(), json=update)).status_code == 422
    assert (await client.patch(f"/api/v1/events/{event_id}", headers=token(), json={"status": "FINISHED"})).status_code == 409


@pytest.mark.parametrize("start", ["2030-08-20T18:00:00Z", "2030-08-21T00:00:00+06:00", "2030-08-20T18:00:00"])
async def test_timezones_and_legacy_date_input(client, token, start):
    response = await client.post("/api/v1/events", headers=token(), json={"title": "Timezone", "start_datetime": start})
    assert response.status_code == 201, response.text
    assert response.json()["starts_at"].startswith("2030-08-20T18:00:00")


async def test_date_order(client, token, event_data):
    event_data["ends_at"] = "2030-08-20T17:00:00Z"
    assert (await client.post("/api/v1/events", headers=token(), json=event_data)).status_code == 422


async def test_outbox_retry_and_republication(client, token, event_data, sessions):
    event_id = (await client.post("/api/v1/events", headers=token(), json=event_data)).json()["id"]
    path = f"/api/v1/events/{event_id}"
    await client.post(path + "/publish", headers=token(), json={"recipient_ids": [str(USER_ID), str(USER_ID)]})
    publisher = AsyncMock()
    publisher.publish.side_effect = RuntimeError("RabbitMQ unavailable")
    with pytest.raises(RuntimeError):
        await deliver_pending(publisher, sessions)
    first_payload = publisher.publish.call_args.args[1]
    assert first_payload["recipient_ids"] == [str(USER_ID)]
    publisher.publish.side_effect = None
    await deliver_pending(publisher, sessions)
    assert publisher.publish.call_args.args[1]["message_id"] == first_payload["message_id"]
    publisher.publish.reset_mock()
    await deliver_pending(publisher, sessions)
    publisher.publish.assert_not_called()
    await client.post(path + "/unpublish", headers=token())
    await client.post(path + "/publish", headers=token())
    await deliver_pending(publisher, sessions)
    payload = publisher.publish.call_args.args[1]
    assert payload["message_id"] != first_payload["message_id"]
    assert payload["audience"] == {"role": "guest", "is_active": True}


async def test_concurrent_publish_creates_one_message(client, token, event_data, sessions):
    import asyncio
    import os
    if not os.environ.get("EVENT_TEST_DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("Requires PostgreSQL row locks")
    event_id = (await client.post("/api/v1/events", headers=token(), json=event_data)).json()["id"]
    results = await asyncio.gather(*[
        client.post(f"/api/v1/events/{event_id}/publish", headers=token()) for _ in range(5)
    ])
    assert all(result.status_code == 200 for result in results)
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(EventOutbox)) == 1
