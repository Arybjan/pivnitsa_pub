import logging
from datetime import timedelta

import httpx

from app.core.config import settings
from app.core.security import encode_token

logger = logging.getLogger(__name__)


class SmsDeliveryError(Exception):
    pass


def mask_phone(phone: str) -> str:
    return f"{phone[:4]}***{phone[-2:]}" if len(phone) > 6 else "***"


async def send_sms(phone: str, message: str) -> None:
    if settings.SMS_PROVIDER == "console":
        logger.warning("SMS (console provider) to %s: %s", mask_phone(phone), message)
        return

    # Notification Service принимает /sms только от role=service/admin — выпускаем короткий служебный токен
    token, _, _ = encode_token(
        "access",
        str(settings.SERVICE_TOKEN_SUBJECT),
        timedelta(minutes=1),
        role="service",
        is_active=True,
        permissions=["notification:write"],
    )
    try:
        async with httpx.AsyncClient(base_url=settings.NOTIFICATION_SERVICE_URL, timeout=5.0) as client:
            response = await client.post(
                "/api/v1/notifications/sms",
                json={"phone_number": phone, "message": message},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("SMS delivery to %s failed: %s", mask_phone(phone), exc)
        raise SmsDeliveryError from exc
