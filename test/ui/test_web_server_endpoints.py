from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

import copium_loop.ui.web_server as web_server
from copium_loop.ui.web_server import app


@pytest.mark.asyncio
async def test_get_status():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/status")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_logs_no_telemetry():
    # Ensure telemetry is None
    original_telemetry = web_server._telemetry
    web_server._telemetry = None
    web_server.set_auth_token("test_token")
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/api/logs", headers={"X-Auth-Token": "test_token"}
            )
            assert response.status_code == 500
            assert response.json() == {"error": "Telemetry not initialized"}
    finally:
        web_server._telemetry = original_telemetry
        web_server.set_auth_token(None)


@pytest.mark.asyncio
async def test_get_logs_with_telemetry():
    mock_telemetry = MagicMock()
    mock_telemetry.read_log.return_value = [{"event_type": "status", "data": "ok"}]

    original_telemetry = web_server._telemetry
    web_server._telemetry = mock_telemetry
    web_server.set_auth_token("test_token")
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/api/logs", headers={"X-Auth-Token": "test_token"}
            )
            assert response.status_code == 200
            assert response.json() == [{"event_type": "status", "data": "ok"}]
    finally:
        web_server._telemetry = original_telemetry
        web_server.set_auth_token(None)


# For Websockets, AsyncClient doesn't support them easily without starlette's TestClient
# But since TestClient is broken, I'll use a different approach or skip for now if I can't fix it easily
# Actually, let's try to mock the websocket part more directly if needed,
# but I want to verify the endpoint logic.
