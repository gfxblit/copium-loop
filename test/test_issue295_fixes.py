from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.__main__ import run_web_server


@pytest.mark.asyncio
async def test_run_web_server_binds_to_localhost():
    """Test that the web server binds to 127.0.0.1 by default."""
    mock_telemetry = MagicMock()
    
    with patch("uvicorn.Config") as mock_config, \
         patch("uvicorn.Server") as mock_server, \
         patch("copium_loop.ui.web_server.initialize_web_server"):
        
        # Setup mock server
        mock_server_instance = AsyncMock()
        mock_server.return_value = mock_server_instance
        
        # Run the server
        await run_web_server(mock_telemetry)
        
        # Verify uvicorn.Config was called with host="127.0.0.1"
        mock_config.assert_called_once()
        args, kwargs = mock_config.call_args
        assert kwargs.get("host") == "127.0.0.1"


def test_telemetry_subscriber_error_is_logged(capsys):
    """Test that if a telemetry subscriber fails, an error is logged to stderr."""
    from copium_loop.telemetry import Telemetry
    
    telemetry = Telemetry("test_session")
    
    def failing_subscriber(event):
        raise ValueError("Subscriber failed!")
        
    telemetry.add_subscriber(failing_subscriber)
    
    # We need to call _write_event directly because it's usually called in a thread
    telemetry._write_event({"test": "data"})
    
    captured = capsys.readouterr()
    assert "Telemetry subscriber" in captured.err
    assert "Subscriber failed!" in captured.err


@pytest.mark.asyncio
async def test_get_architect_prompt_sanitization():
    """Test that untrusted git data is sanitized in the architect prompt."""
    from copium_loop.nodes.utils import get_architect_prompt
    
    state = {
        "initial_commit_hash": "abcdef123",
        "head_hash": "HEAD",
    }
    
    mock_engine = MagicMock()
    mock_engine.engine_type = "gemini"
    # Mock sanitize_for_prompt to actually do some sanitization for testing
    def mock_sanitize(text, max_length=12000):
        return text.replace("<tag>", "[tag]")
    mock_engine.sanitize_for_prompt.side_effect = mock_sanitize
    
    # We need to mock the git functions called by get_architect_prompt
    with patch("copium_loop.nodes.utils.get_diff", return_value="<tag>malicious</tag>"), \
         patch("copium_loop.nodes.utils.get_commit_summary", return_value="<tag>malicious summary</tag>"), \
         patch("copium_loop.nodes.utils.get_diff_stat", return_value="<tag>malicious stat</tag>"), \
         patch("copium_loop.nodes.utils.is_git_repo", return_value=True):
        
        # This will fail if get_architect_prompt doesn't take engine yet
        try:
            prompt = await get_architect_prompt("gemini", state, engine=mock_engine)
        except TypeError:
            # Expected failure before fix
            pytest.fail("get_architect_prompt does not take 'engine' argument yet")
            
        assert "[tag]malicious" in prompt
        assert "<tag>malicious" not in prompt


def test_api_logs_requires_auth():
    """Test that /api/logs requires authentication."""
    from fastapi.testclient import TestClient
    from copium_loop.ui.web_server import app, set_auth_token
    
    set_auth_token("secret-token")
    client = TestClient(app)
    
    # Request without token
    response = client.get("/api/logs")
    assert response.status_code == 403
    
    # Request with wrong token
    response = client.get("/api/logs", headers={"X-Auth-Token": "wrong-token"})
    assert response.status_code == 403
    
    # Request with correct token
    # We need to mock telemetry for this to succeed (200)
    with patch("copium_loop.ui.web_server._telemetry") as mock_telemetry:
        mock_telemetry.read_log.return_value = []
        response = client.get("/api/logs", headers={"X-Auth-Token": "secret-token"})
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_websocket_requires_auth():
    """Test that the WebSocket endpoint requires the correct token."""
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from copium_loop.ui.web_server import app, set_auth_token
    
    set_auth_token("secret-token")
    client = TestClient(app)
    
    # WebSocket connection without token should fail with policy violation (1008)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/ws") as websocket:
            pass
    assert exc.value.code == 1008
        
    # Wrong token should also fail
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/api/ws?token=wrong-token") as websocket:
             pass
    assert exc.value.code == 1008

    # Correct token should work
    with client.websocket_connect("/api/ws?token=secret-token") as websocket:
        # Should be open
        assert True
