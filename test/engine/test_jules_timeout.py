from unittest.mock import MagicMock, patch

import httpx
import pytest

from copium_loop.engine.jules import (
    JulesEngine,
    JulesTimeoutError,
)


@pytest.mark.asyncio
async def test_jules_api_inactivity_timeout_reset():
    """
    Test that seeing new activities resets the inactivity timer.
    We set a total timeout of 100 and inactivity timeout of 10.
    We report an activity at t=5.
    At t=11, it should NOT have timed out because the inactivity timer was reset at t=5.
    """
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.engine.jules.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.get_running_loop") as mock_get_loop,
        patch("asyncio.sleep", return_value=None),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock responses:
        # 1. Activity poll at t=0: no activities
        # 2. State poll at t=0: ACTIVE
        # 3. Activity poll at t=5: one new activity
        # 4. State poll at t=5: ACTIVE
        # 5. Activity poll at t=11: same activity
        # 6. State poll at t=11: ACTIVE
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),  # 1
            httpx.Response(200, json={"state": "ACTIVE"}),  # 2
            httpx.Response(
                200, json={"activities": [{"id": "act1", "description": "Progress"}]}
            ),  # 3
            httpx.Response(200, json={"state": "ACTIVE"}),  # 4
            httpx.Response(
                200, json={"activities": [{"id": "act1", "description": "Progress"}]}
            ),  # 5
            httpx.Response(200, json={"state": "ACTIVE"}),  # 6
        ]

        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        # Time calls:
        # Initial: start_time = 0
        # Loop 1 (t=0): current_time = 0. (0-0 <= 100, 0-0 <= 10)
        # Loop 2 (t=5): current_time = 5. (5-0 <= 100, 5-0 <= 10). Sees activity, last_activity_time = 5.
        # Loop 3 (t=11): current_time = 11. (11-0 <= 100, 11-5 <= 10). Still OK!
        # Loop 4 (t=20): current_time = 20. (20-0 <= 100, 20-5 > 10). TIMEOUT!
        mock_loop.time.side_effect = [
            0,  # start_time
            0,  # Loop 1 current_time
            5,  # Loop 2 current_time
            11,  # Loop 3 current_time
            20,  # Loop 4 current_time
        ]

        # We need to run it in a way that it eventually times out so we can assert it
        with pytest.raises(JulesTimeoutError, match="inactivity timeout: 10s"):
            await engine.invoke(
                "Test prompt", command_timeout=100, inactivity_timeout=10
            )

        # Check that it reached at least the 3rd loop (6th GET call)
        assert client.get.call_count >= 6
