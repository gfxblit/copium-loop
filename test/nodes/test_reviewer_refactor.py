from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import reviewer_node


@pytest.mark.asyncio
async def test_reviewer_implicit_verdict_approved(agent_state):
    """Test that reviewer recognizes the current magic string (to be refactored)."""
    agent_state[
        "engine"
    ].invoke.return_value = "Some summary\nIMPLICIT_VERDICT: APPROVED"
    agent_state["test_output"] = "PASS"
    agent_state["initial_commit_hash"] = "abc"

    with patch(
        "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
    ) as mock_get_diff:
        mock_get_diff.return_value = "some diff"
        result = await reviewer_node.reviewer_node(agent_state)

    assert result["review_status"] == "approved"


@pytest.mark.asyncio
async def test_reviewer_approved_by_changeset_in_state(agent_state):
    """
    Test that reviewer approves if a changeset is detected in the state,
    even if the engine output doesn't contain a verdict.
    This is the desired behavior for the refactor.
    """
    # Simulate Jules session that produced a changeset
    agent_state["engine"].invoke.return_value = "Jules finished the task."
    agent_state["test_output"] = "PASS"
    agent_state["initial_commit_hash"] = "abc"

    agent_state["has_changeset"] = True

    with patch(
        "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
    ) as mock_get_diff:
        mock_get_diff.return_value = "some diff"
        result = await reviewer_node.reviewer_node(agent_state)

    assert result["review_status"] == "approved"
