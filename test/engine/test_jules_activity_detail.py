from unittest.mock import patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_poll_session_detailed_activities():
    """Verify that _poll_session extracts more detail from various activity types."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry") as mock_get_telemetry,
        patch("builtins.print"),
    ):
        client = mock_client.return_value.__aenter__.return_value
        mock_telemetry = mock_get_telemetry.return_value

        # Mock activity responses with more detailed types
        client.get.side_effect = [
            # First poll for activities
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "planGenerated": {
                                "plan": {"steps": [{"description": "Step 1"}]}
                            },
                        },
                        {
                            "id": "act2",
                            "toolCallStarted": {
                                "toolName": "ls",
                                "args": {"path": "."},
                            },
                        },
                        {
                            "id": "act3",
                            "toolCallCompleted": {
                                "toolName": "ls",
                                "output": "file1.txt",
                            },
                        },
                        {"id": "act4", "text": "Generic text message"},
                        {"id": "act5"},
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
            verbose=True,
        )

        # We expect detailed messages for each
        # Depending on implementation, we might want to verify specific strings
        calls = [call.args[1] for call in mock_telemetry.log_output.call_args_list]

        # act5 should be filtered
        assert len(calls) == 4

        # Check if we got more than just "Activity update"
        for call in calls:
            assert (
                "Activity update" not in call or "ls" in call or "plan" in call.lower()
            )
