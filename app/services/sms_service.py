import re
import uuid
import logging
import httpx
from xml.sax.saxutils import escape
from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_sms_via_nikita(phone_number: str, message: str) -> bool:
    clean_phone = re.sub(r"\D", "", phone_number)
    if not clean_phone:
        logger.error(f"Invalid phone number provided: {phone_number}")
        return False

    message_id = uuid.uuid4().hex[:12]
    test_tag = "<test>1</test>" if settings.NIKITA_TEST_MODE else ""

    xml_payload = f"""<?xml version="1.0" encoding="UTF-8"?>
<message>
    <login>{escape(settings.NIKITA_LOGIN)}</login>
    <pwd>{escape(settings.NIKITA_PASSWORD)}</pwd>
    <id>{message_id}</id>
    <sender>{escape(settings.NIKITA_SENDER)}</sender>
    <text>{escape(message)}</text>
    <phones>
        <phone>{clean_phone}</phone>
    </phones>
    {test_tag}
</message>"""

    headers = {"Content-Type": "application/xml; charset=utf-8"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                settings.NIKITA_API_URL,
                content=xml_payload.encode("utf-8"),
                headers=headers
            )
            response.raise_for_status()
            logger.info(f"Nikita SMS response for {clean_phone}: {response.text}")
            if "<status>0</status>" in response.text or "<status>00</status>" in response.text:
                return True
            return False
    except Exception as e:
        logger.error(f"Failed to send SMS via Nikita to {clean_phone}: {e}")
        return False