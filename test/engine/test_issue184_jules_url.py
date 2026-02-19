from unittest.mock import patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine, JulesSessionError


@pytest.mark.asyncio
async def test_get_session_url():
    engine = JulesEngine()
    # Test with standard session name
    session_name = "sessions/1278697959791104912"
    expected_url = "https://jules.google.com/session/1278697959791104912"
    assert engine._get_session_url(session_name) == expected_url

    # Test with just ID (though API usually returns sessions/ prefix)
    assert engine._get_session_url("123") == "https://jules.google.com/session/123"


@pytest.mark.asyncio
async def test_jules_invoke_logs_url():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry") as mock_get_telemetry,
        patch("builtins.print") as mock_print,
    ):
        client = mock_client.return_value.__aenter__.return_value
        mock_telemetry = mock_get_telemetry.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(201, json={"name": "sessions/123"})

        # Mock polling
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine.invoke("Test prompt", node="architect", verbose=True)

        expected_url = "https://jules.google.com/session/123"

        # Verify stdout
        mock_print.assert_any_call(f"Jules session created: {expected_url}")

        # Verify telemetry
        mock_telemetry.log_output.assert_any_call(
            "architect", f"Jules session created: {expected_url}\n"
        )


@pytest.mark.asyncio
async def test_jules_poll_session_error_includes_url():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock activity polling (1st) and failing session polling (2nd)
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "FAILED", "name": "sessions/123"}),
        ]

        expected_url = "https://jules.google.com/session/123"
        with pytest.raises(
            JulesSessionError, match=f"Jules session {expected_url} failed"
        ):
            await engine._poll_session(
                client, "sessions/123", timeout=10, inactivity_timeout=5
            )
