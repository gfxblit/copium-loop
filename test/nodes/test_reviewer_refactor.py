from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import reviewer_node


@pytest.mark.asyncio
async def test_reviewer_approved_by_standard_verdict(agent_state):
    """Test that reviewer approves when standard VERDICT: APPROVED is present."""
    agent_state["engine"].invoke.return_value = "Some summary\nVERDICT: APPROVED"
    agent_state["test_output"] = "PASS"
    agent_state["initial_commit_hash"] = "abc"

    with patch(
        "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
    ) as mock_get_diff:
        mock_get_diff.return_value = "some diff"
        result = await reviewer_node.reviewer_node(agent_state)

    assert result["review_status"] == "approved"


@pytest.mark.asyncio
async def test_reviewer_no_auto_approval_without_verdict(agent_state):
    """
    Test that reviewer does NOT approve if there is no verdict,
    even if we used to have a changeset in state.
    """
    agent_state[
        "engine"
    ].invoke.return_value = "Jules finished the task but no verdict."
    agent_state["test_output"] = "PASS"
    agent_state["initial_commit_hash"] = "abc"

    # Even if has_changeset is set (it shouldn't be in the final state),
    # the reviewer should NOT use it anymore.
    agent_state["has_changeset"] = True

    with patch(
        "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
    ) as mock_get_diff:
        mock_get_diff.return_value = "some diff"
        result = await reviewer_node.reviewer_node(agent_state)

    # In the current (broken) implementation this would be 'approved'
    # but we want it to fail to find a verdict.
    assert result["review_status"] == "error"
