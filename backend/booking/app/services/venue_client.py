import logging
import os

import httpx


logger = logging.getLogger(__name__)

# Venue Service: номера столов для ответов. Пусто - номера не подставляются
VENUE_SERVICE_URL = os.getenv("VENUE_SERVICE_URL", "http://venue:8000")
VENUE_SERVICE_TIMEOUT = float(os.getenv("VENUE_SERVICE_TIMEOUT", "3"))


def get_table_details(table_ids: set[int]) -> dict[int, dict]:
    """Детали столов {table_id: {number, price}} одним запросом к Venue Service."""
    if not VENUE_SERVICE_URL or not table_ids:
        return {}

    try:
        response = httpx.get(
            f"{VENUE_SERVICE_URL}/api/v1/tables/numbers",
            params=[("id", table_id) for table_id in sorted(table_ids)],
            timeout=VENUE_SERVICE_TIMEOUT,
        )
        response.raise_for_status()
        return {item["id"]: item for item in response.json()}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Table details are unavailable: %s", exc)
        return {}


def get_table_numbers(table_ids: set[int]) -> dict[int, int]:
    details = get_table_details(table_ids)
    return {tid: d.get("number") for tid, d in details.items() if d.get("number") is not None}
