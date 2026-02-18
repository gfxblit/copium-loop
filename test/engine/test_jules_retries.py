from unittest.mock import MagicMock, patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine, JulesSessionError


@pytest.mark.asyncio
async def test_request_with_retry_success_after_failure():
    """Verify that _request_with_retry eventually succeeds after transient failures."""
    engine = JulesEngine()

    with (
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch(
            "copium_loop.engine.jules.wait_exponential", return_value=MagicMock()
        ),  # Speed up tests
    ):
        mock_client = MagicMock(spec=httpx.AsyncClient)

        # Fail twice with ConnectError, then succeed
        mock_client.get.side_effect = [
            httpx.ConnectError("Connection failed"),
            httpx.ConnectError("Connection failed again"),
            httpx.Response(200, json={"success": True}),
        ]

        resp = await engine._request_with_retry(
            "Context", mock_client.get, "http://example.com"
        )
        assert resp.status_code == 200
        assert mock_client.get.call_count == 3


@pytest.mark.asyncio
async def test_request_with_retry_exhaustion():
    """Verify that _request_with_retry raises JulesSessionError after exhausting retries."""
    engine = JulesEngine()

    with (
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("copium_loop.engine.jules.wait_exponential", return_value=MagicMock()),
    ):
        mock_client = MagicMock(spec=httpx.AsyncClient)

        # Always fail
        mock_client.get.side_effect = httpx.ConnectError("Permanent failure")

        with pytest.raises(JulesSessionError, match="Context: Permanent failure"):
            await engine._request_with_retry(
                "Context", mock_client.get, "http://example.com"
            )

        # 1 initial call + 3 retries = 4 calls
        assert mock_client.get.call_count == 4


@pytest.mark.asyncio
async def test_request_with_retry_no_retry_on_4xx():
    """Verify that _request_with_retry does NOT retry on 4xx errors (client errors)."""
    engine = JulesEngine()

    with (
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
    ):
        mock_client = MagicMock(spec=httpx.AsyncClient)

        # HTTP 404 is a successful request as far as httpx is concerned (no exception)
        mock_client.get.return_value = httpx.Response(404, text="Not Found")

        resp = await engine._request_with_retry(
            "Context", mock_client.get, "http://example.com"
        )
        assert resp.status_code == 404
        assert mock_client.get.call_count == 1
