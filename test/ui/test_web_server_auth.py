from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

import copium_loop.ui.web_server as web_server
from copium_loop.ui.web_server import app, set_auth_token


@pytest.mark.asyncio
async def test_api_auth_success():
    set_auth_token("secret_token")
    mock_telemetry = MagicMock()
    mock_telemetry.read_log.return_value = [{"event_type": "status", "data": "ok"}]

    original_telemetry = web_server._telemetry
    web_server._telemetry = mock_telemetry
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # Valid token
            response = await client.get(
                "/api/logs", headers={"X-Auth-Token": "secret_token"}
            )
            assert response.status_code == 200
            assert response.json() == [{"event_type": "status", "data": "ok"}]
    finally:
        web_server._telemetry = original_telemetry
        set_auth_token(None)


@pytest.mark.asyncio
async def test_api_auth_failure():
    set_auth_token("secret_token")
    mock_telemetry = MagicMock()

    original_telemetry = web_server._telemetry
    web_server._telemetry = mock_telemetry
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            # Invalid token
            response = await client.get(
                "/api/logs", headers={"X-Auth-Token": "wrong_token"}
            )
            assert response.status_code == 403
            assert response.json() == {"detail": "Invalid auth token"}

            # Missing token
            response = await client.get("/api/logs")
            assert response.status_code == 403
    finally:
        web_server._telemetry = original_telemetry
        set_auth_token(None)


@pytest.mark.asyncio
async def test_ws_auth_success():
    set_auth_token("secret_token")
    client = TestClient(app)
    with client.websocket_connect("/api/ws?token=secret_token"):
        # If it didn't raise, it's successful
        pass
    set_auth_token(None)


@pytest.mark.asyncio
async def test_ws_auth_failure():
    set_auth_token("secret_token")
    client = TestClient(app)
    # Starlette raises if handshake fails.
    with pytest.raises(Exception), client.websocket_connect("/api/ws?token=wrong_token"):  # noqa: B017
        pass
    set_auth_token(None)


@pytest.mark.asyncio
async def test_ws_auth_missing_token():
    set_auth_token("secret_token")
    client = TestClient(app)
    with pytest.raises(Exception), client.websocket_connect("/api/ws"):  # noqa: B017
        pass
    set_auth_token(None)
