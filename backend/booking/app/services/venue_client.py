import logging
import os

import httpx


logger = logging.getLogger(__name__)

# Venue Service: номера столов для ответов. Пусто - номера не подставляются
VENUE_SERVICE_URL = os.getenv("VENUE_SERVICE_URL", "")
VENUE_SERVICE_TIMEOUT = float(os.getenv("VENUE_SERVICE_TIMEOUT", "3"))


def get_table_numbers(table_ids: set[int]) -> dict[int, int]:
    """Номера столов {table_id: number} одним запросом к Venue Service.

    Столы хранятся в другом сервисе и другой БД, поэтому номер берётся
    пакетным запросом на весь ответ, а не по одному на бронь.
    Если Venue недоступен или стол не найден, номера для него нет:
    бронь всё равно отдаётся, просто с table_number = null.
    """
    if not VENUE_SERVICE_URL or not table_ids:
        return {}

    try:
        response = httpx.get(
            f"{VENUE_SERVICE_URL}/api/v1/tables/numbers",
            params=[("id", table_id) for table_id in sorted(table_ids)],
            timeout=VENUE_SERVICE_TIMEOUT,
        )
        response.raise_for_status()
        return {item["id"]: item["number"] for item in response.json()}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Table numbers are unavailable: %s", exc)
        return {}
