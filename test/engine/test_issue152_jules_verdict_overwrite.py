from unittest.mock import MagicMock, patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_poll_session_verdict_preservation():
    """Verify that _poll_session preserves a verdict buried in a description and doesn't overwrite it with generic text."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry") as mock_get_telemetry,
        patch("builtins.print"),
    ):
        client = mock_client.return_value.__aenter__.return_value
        
        # Mock activity responses
        # 1. Activity with verdict in description
        # 2. Activity with "Session completed" title but no description
        client.get.side_effect = [
            # First poll for activities
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Reviewing code",
                                "description": "User's Goal: ... Analysis: ... VERDICT: REFACTOR because of reasons."
                            }
                        }
                    ]
                },
            ),
            # First poll for session state (STILL RUNNING to allow second poll)
            httpx.Response(200, json={"state": "RUNNING"}),
            # Second poll for activities
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Reviewing code",
                                "description": "User's Goal: ... Analysis: ... VERDICT: REFACTOR because of reasons."
                            }
                        },
                        {
                            "id": "act2",
                            "sessionCompleted": {}
                        }
                    ]
                },
            ),
            # Second poll for session state (COMPLETED)
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        status_data = await engine._poll_session(
            client,
            "sessions/sess_123",
            timeout=10,
            inactivity_timeout=5,
            node="test_node",
            verbose=True,
        )

        # The summary should be from act1 because it contains VERDICT: REFACTOR
        # even though act2 came after it.
        # In the actual status_data returned, _poll_session injects the last_summary
        # into activities[0]["description"] if it's missing.
        assert "activities" in status_data
        summary = status_data["activities"][0]["description"]
        assert "VERDICT: REFACTOR" in summary
        assert "Session completed" not in summary

@pytest.mark.asyncio
async def test_poll_session_verdict_anywhere_in_text():
    """Verify that 'VERDICT:' anywhere in text is preserved."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("builtins.print"),
    ):
        client = mock_client.return_value.__aenter__.return_value
        
        client.get.side_effect = [
            # First poll: Verdict in title
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Final Verdict: VERDICT: OK",
                            }
                        }
                    ]
                },
            ),
            httpx.Response(200, json={"state": "RUNNING"}),
            # Second poll: Generic description
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Final Verdict: VERDICT: OK",
                            }
                        },
                        {
                            "id": "act2",
                            "progressUpdated": {
                                "description": "Cleaning up resources..."
                            }
                        }
                    ]
                },
            ),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        status_data = await engine._poll_session(
            client, "sessions/sess_123", timeout=10, inactivity_timeout=5
        )

        summary = status_data["activities"][0]["description"]
        assert "VERDICT: OK" in summary
        assert "Cleaning up" not in summary
