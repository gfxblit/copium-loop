from unittest.mock import AsyncMock, patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_jules_sets_has_changeset_in_state():
    """Verify that JulesEngine sets has_changeset in state when artifacts are produced."""
    engine = JulesEngine()
    state = {"has_changeset": False}

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation
        client.post.return_value = httpx.Response(201, json={"name": "sess"})

        # Mock session polling success with changeSet
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(
                200,
                json={
                    "state": "COMPLETED",
                    "outputs": [
                        {
                            "changeSet": {
                                "gitPatch": {
                                    "unidiffPatch": "patch content",
                                }
                            }
                        }
                    ],
                },
            ),
        ]

        # Use patch to avoid coder-specific git push/pull logic if necessary
        with patch("copium_loop.engine.jules.git", new_callable=AsyncMock):
            await engine.invoke("Test prompt", node="reviewer", state=state)

        assert state["has_changeset"] is True


@pytest.mark.asyncio
async def test_jules_extract_summary_standard_verdict():
    """Verify that JulesEngine._extract_summary uses IMPLICIT_VERDICT: APPROVED."""
    engine = JulesEngine()

    status_data = {
        "outputs": [{"changeSet": {"gitPatch": {"unidiffPatch": "diff"}}}],
        "activities": [{"description": "Work done"}],
    }

    summary = engine._extract_summary(status_data)
    assert "IMPLICIT_VERDICT: APPROVED" in summary
