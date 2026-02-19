from unittest.mock import patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_poll_session_truncates_large_outputs():
    """Verify that _poll_session truncates very large activity details in telemetry."""
    engine = JulesEngine()

    large_args = {"content": "A" * 5000}
    large_message = "M" * 5000

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry") as mock_get_telemetry,
        patch("builtins.print"),
    ):
        client = mock_client.return_value.__aenter__.return_value
        mock_telemetry = mock_get_telemetry.return_value

        client.get.side_effect = [
            # First poll for activities
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "toolCallStarted": {
                                "toolName": "write_file",
                                "args": large_args,
                            },
                        },
                        {
                            "id": "act2",
                            "agentMessaged": {
                                "message": large_message,
                            },
                        },
                    ]
                },
            ),
            # First poll for session state
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine._poll_session(
            client,
            "sessions/sess_123",
            timeout=10,
            inactivity_timeout=5,
            node="test_node",
            verbose=False,
        )

        # Verify telemetry log_output was called
        assert mock_telemetry.log_output.called
        calls = [call.args[1] for call in mock_telemetry.log_output.call_args_list]

        for call in calls:
            # Each call should be reasonably short, around the MAX_TELEMETRY_LOG_LENGTH (1000)
            # plus some overhead for the title and suffix.
            assert len(call) < 1200
            assert "... (truncated)" in call
