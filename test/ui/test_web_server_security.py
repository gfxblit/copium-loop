from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

import copium_loop.ui.web_server as web_server
from copium_loop.ui.web_server import app, set_auth_token


@pytest.mark.asyncio
async def test_api_no_token_set_fails():
    # If no token is set, it should NOT allow access if we want to be secure by default
    set_auth_token(None)
    mock_telemetry = MagicMock()

    original_telemetry = web_server._telemetry
    web_server._telemetry = mock_telemetry
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get("/api/logs")
            # If we enforce authentication, this should be 403
            assert response.status_code == 403
            assert response.json() == {"detail": "Authentication token required"}
    finally:
        web_server._telemetry = original_telemetry
