from unittest.mock import AsyncMock, MagicMock

import pytest
from app.api.v1.endpoints import health

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("db_ready,redis_ready,code", [(True, True, 200), (False, True, 503), (True, False, 503), (False, False, 503)])
async def test_readiness(client, monkeypatch, db_ready, redis_ready, code):
    connection = AsyncMock()
    if not db_ready:
        connection.execute.side_effect = RuntimeError("database unavailable")
    engine = MagicMock()
    engine.connect.return_value.__aenter__ = AsyncMock(return_value=connection)
    engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)
    redis = AsyncMock()
    if not redis_ready:
        redis.ping.side_effect = RuntimeError("redis unavailable")
    monkeypatch.setattr(health, "engine", engine)
    monkeypatch.setattr(health, "redis_client", redis)
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == code
    assert response.json()["checks"] == {"database": db_ready, "redis": redis_ready}
    assert str(connection.execute.call_args.args[0]) == "SELECT 1"
