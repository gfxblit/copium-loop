from unittest.mock import patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.nodes import architect, reviewer
from copium_loop.nodes.utils import get_architect_prompt, get_reviewer_prompt


@pytest.mark.asyncio
async def test_get_architect_prompt(agent_state):
    """Verify architect prompt generation for different engines."""
    agent_state["initial_commit_hash"] = "sha123"

    # Test Jules prompt
    with patch("copium_loop.nodes.utils.is_git_repo", return_value=True):
        jules_prompt = await get_architect_prompt("jules", agent_state)
        assert "sha123" in jules_prompt
        assert "git diff" in jules_prompt.lower()
        assert "JULES_OUTPUT.txt" not in jules_prompt

    # Test Gemini prompt
    with (
        patch("copium_loop.nodes.utils.is_git_repo", return_value=True),
        patch(
            "copium_loop.nodes.utils.get_diff", return_value="some diff"
        ) as mock_get_diff,
    ):
        gemini_prompt = await get_architect_prompt("gemini", agent_state)
        assert "some diff" in gemini_prompt
        mock_get_diff.assert_called_with("sha123", head=None, node="architect")


@pytest.mark.asyncio
async def test_get_reviewer_prompt(agent_state):
    """Verify reviewer prompt generation for different engines."""
    agent_state["initial_commit_hash"] = "sha123"
    agent_state["test_output"] = "PASS"

    # Test Jules prompt
    with patch("copium_loop.nodes.utils.is_git_repo", return_value=True):
        jules_prompt = await get_reviewer_prompt("jules", agent_state)
        assert "sha123" in jules_prompt
        assert "git diff" in jules_prompt.lower()
        assert "JULES_OUTPUT.txt" not in jules_prompt

    # Test Gemini prompt
    with (
        patch("copium_loop.nodes.utils.is_git_repo", return_value=True),
        patch(
            "copium_loop.nodes.utils.get_diff", return_value="some diff"
        ) as mock_get_diff,
    ):
        gemini_prompt = await get_reviewer_prompt("gemini", agent_state)
        assert "some diff" in gemini_prompt
        mock_get_diff.assert_called_with("sha123", head=None, node="reviewer")


@pytest.mark.asyncio
async def test_architect_node_engine_agnostic(agent_state):
    """Verify Architect node is engine-agnostic and doesn't use JULES_OUTPUT.txt."""
    agent_state["engine"].engine_type = "jules"
    agent_state["engine"].invoke.return_value = "VERDICT: OK"
    agent_state["messages"] = [HumanMessage(content="test")]
    agent_state["initial_commit_hash"] = "sha123"

    with (
        patch(
            "copium_loop.nodes.architect_node.get_architect_prompt",
            return_value="mock prompt",
        ) as mock_get_prompt,
    ):
        result = await architect(agent_state)

        mock_get_prompt.assert_called_once()
        agent_state["engine"].invoke.assert_called_once()
        args, kwargs = agent_state["engine"].invoke.call_args
        assert args[0] == "mock prompt"
        assert "sync_strategy" not in kwargs
        assert result["architect_status"] == "ok"


@pytest.mark.asyncio
async def test_reviewer_node_engine_agnostic(agent_state):
    """Verify Reviewer node is engine-agnostic and doesn't use JULES_OUTPUT.txt."""
    agent_state["engine"].engine_type = "jules"
    agent_state["engine"].invoke.return_value = "VERDICT: APPROVED"
    agent_state["messages"] = [HumanMessage(content="test")]
    agent_state["initial_commit_hash"] = "sha123"

    with (
        patch(
            "copium_loop.nodes.reviewer_node.get_reviewer_prompt",
            return_value="mock prompt",
        ) as mock_get_prompt,
    ):
        result = await reviewer(agent_state)

        mock_get_prompt.assert_called_once()
        agent_state["engine"].invoke.assert_called_once()
        args, kwargs = agent_state["engine"].invoke.call_args
        assert args[0] == "mock prompt"
        assert "sync_strategy" not in kwargs
        assert result["review_status"] == "approved"
