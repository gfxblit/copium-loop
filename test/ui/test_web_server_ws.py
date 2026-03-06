import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import copium_loop.ui.web_server as web_server


@pytest.fixture
def telemetry_mock():
    mock = MagicMock()
    mock.read_log.return_value = [{"event_type": "status", "node": "coder", "data": "active", "timestamp": "2024-01-01T00:00:00"}]
    return mock

@pytest.mark.asyncio
async def test_websocket_broadcast():
    # This one tests the actual broadcast mechanism

    # Mock a websocket
    mock_ws = MagicMock()
    mock_ws.send_json = AsyncMock()

    web_server._active_websockets.add(mock_ws)

    # Mock the event loop
    loop = asyncio.get_running_loop()
    with patch("copium_loop.ui.web_server._loop", loop):
        event = {"node": "tester", "event_type": "status", "data": "active"}
        web_server.broadcast_telemetry_event(event)

        # Since it's run_coroutine_threadsafe, we need to wait a bit
        await asyncio.sleep(0.1)

        mock_ws.send_json.assert_called_with(event)

    web_server._active_websockets.discard(mock_ws)

@pytest.mark.asyncio
async def test_initialize_web_server(telemetry_mock):
    web_server.initialize_web_server(telemetry_mock)
    assert web_server._telemetry == telemetry_mock
    telemetry_mock.add_subscriber.assert_called_once()
