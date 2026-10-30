import os
from datetime import datetime, timezone

import httpx


# Event Service: дата мероприятия для брони из приложения. Пусто - проверка отключена
EVENT_SERVICE_URL = os.getenv("EVENT_SERVICE_URL", "")


class EventNotBookable(Exception):
    pass


class EventServiceUnavailable(Exception):
    pass


def get_bookable_event_start(event_id: int) -> datetime | None:
    """Начало опубликованного и ещё не начавшегося мероприятия.

    Без авторизации Event Service отдаёт только опубликованные мероприятия,
    поэтому черновики и отменённые сюда не попадают.
    """
    if not EVENT_SERVICE_URL:
        return None

    try:
        response = httpx.get(f"{EVENT_SERVICE_URL}/api/v1/events/{event_id}", timeout=5.0)
    except httpx.HTTPError as exc:
        raise EventServiceUnavailable from exc

    if response.status_code == 404:
        raise EventNotBookable("Event not found")
    if response.status_code != 200:
        raise EventServiceUnavailable(f"Event Service responded {response.status_code}")

    starts_at = datetime.fromisoformat(response.json()["starts_at"].replace("Z", "+00:00"))
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)

    if starts_at <= datetime.now(timezone.utc):
        raise EventNotBookable("Event has already started")

    return starts_at
