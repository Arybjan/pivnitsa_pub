import logging
import os

import httpx


logger = logging.getLogger(__name__)

# Venue Service: номера столов для ответов API. Пусто - номера не подставляются
VENUE_SERVICE_URL = os.getenv("VENUE_SERVICE_URL", "")

# Venue отдаёт до 200 столов за запрос
BATCH_SIZE = 200


def get_table_numbers(table_ids: list[int]) -> dict[int, int]:
    """Номера столов по ID одним запросом на каждые BATCH_SIZE столов.

    Номер нужен только для отображения, поэтому недоступный Venue Service
    не ломает ответ: для таких столов номер просто не возвращается.
    Удалённых столов Venue не отдаёт - у них номера тоже не будет.
    """
    unique_ids = list(dict.fromkeys(table_ids))
    if not VENUE_SERVICE_URL or not unique_ids:
        return {}

    numbers: dict[int, int] = {}
    for start in range(0, len(unique_ids), BATCH_SIZE):
        chunk = unique_ids[start:start + BATCH_SIZE]
        params = [("id", table_id) for table_id in chunk] + [("limit", BATCH_SIZE)]
        try:
            response = httpx.get(
                f"{VENUE_SERVICE_URL}/api/v1/tables",
                params=params,
                timeout=3.0,
            )
            response.raise_for_status()
            numbers.update({table["id"]: table["number"] for table in response.json()})
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            logger.warning("Venue Service table lookup failed: %s", exc)
            break

    return numbers
