from unittest.mock import patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_jules_truncation_fix_repro():
    """
    Reproduce issue #168: Jules output is truncated at 1000 characters,
    causing verdicts at the end of long messages to be lost.
    """
    engine = JulesEngine()

    # 1500 characters followed by a verdict.
    # The total length is > 1000, so it should be truncated if the bug exists.
    verdict = "VERDICT: REJECTED"
    long_description = "A" * 1500 + " " + verdict

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock activity polling with long description
        client.get.side_effect = [
            # Activity poll
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "agentMessaged": {"agentMessage": long_description},
                        }
                    ]
                },
            ),
            # Session state poll
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        result = await engine.invoke("Test prompt", node="reviewer")

        # If it's truncated, the verdict will be lost.
        assert verdict in result, (
            f"Verdict '{verdict}' not found in result: {result[:100]}..."
        )


@pytest.mark.asyncio
async def test_jules_truncation_telemetry_still_truncated():
    """
    Verify that while the return value is NOT truncated,
    the telemetry output STILL IS truncated (as per proposed fix).
    """
    engine = JulesEngine()

    # Use a different constant name if we already renamed it, but for now use 1000
    MAX_LOG_LENGTH = 1000
    long_description = "B" * (MAX_LOG_LENGTH + 500)

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry") as mock_get_telemetry,
    ):
        client = mock_client.return_value.__aenter__.return_value
        mock_telemetry = mock_get_telemetry.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock activity polling
        client.get.side_effect = [
            # Activity poll
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "agentMessaged": {"agentMessage": long_description},
                        }
                    ]
                },
            ),
            # Session state poll
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine.invoke("Test prompt", node="reviewer")

        # Check telemetry.log_output calls
        # We expect it to be called with truncated description
        log_calls = [call.args[1] for call in mock_telemetry.log_output.call_args_list]
        found_truncated = False
        for msg in log_calls:
            if "... (truncated)" in msg:
                found_truncated = True
                # It should be around 1000 chars + some extra for "Agent message: " and "... (truncated)"
                assert len(msg) < 1100
                break

        assert found_truncated, "Telemetry output was not truncated"
