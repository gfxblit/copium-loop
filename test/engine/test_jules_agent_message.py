from unittest.mock import patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_jules_api_agent_message_extraction():
    """Verify that the Jules engine correctly extracts the summary from the 'agentMessage' field."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock activity polling with agentMessage instead of message/text
        client.get.side_effect = [
            # First poll: Activity update with agentMessage
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "1",
                            "agentMessaged": {
                                "agentMessage": "VERDICT: OK - This is from agentMessage"
                            },
                        }
                    ]
                },
            ),
            # First poll: Session state is COMPLETED
            httpx.Response(
                200,
                json={
                    "name": "sessions/sess_123",
                    "state": "COMPLETED",
                    "outputs": [],
                },
            ),
        ]

        # Use architect node because it doesn't trigger git pull/push in the mock
        result = await engine.invoke("Test prompt", node="architect")

        assert "VERDICT: OK - This is from agentMessage" in result
        assert (
            "Agent message" not in result
        )  # Should not be the fallback title if desc is found
