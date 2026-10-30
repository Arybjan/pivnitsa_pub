import logging
from datetime import datetime
from typing import Any, Dict

import httpx
from fastapi import HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


class BookingServiceClient:
    """
    Читает бронь из Booking Service от имени пользователя (его же токеном).
    Booking Service сам отвечает 403 на чужую бронь, поэтому владелец проверяется дважды.
    """

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        # transport подменяется в тестах
        self._transport = transport

    async def get_booking(self, booking_id: int, token: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=settings.BOOKING_SERVICE_URL,
                timeout=settings.BOOKING_SERVICE_TIMEOUT,
                transport=self._transport,
            ) as client:
                response = await client.get(
                    f"/api/v1/bookings/{booking_id}",
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.HTTPError as exc:
            logger.error("Booking Service is unavailable: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Booking Service is unavailable",
            )

        if response.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found")
        if response.status_code == status.HTTP_403_FORBIDDEN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Booking belongs to another user")
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Booking Service rejected the token")
        if response.status_code != status.HTTP_200_OK:
            logger.error("Unexpected Booking Service response %s: %s", response.status_code, response.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unexpected Booking Service response",
            )

        return response.json()


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


booking_client = BookingServiceClient()
