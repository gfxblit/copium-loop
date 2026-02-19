import sys
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.memory import MemoryManager
from copium_loop.nodes import architect, coder, reviewer

architect_module = sys.modules["copium_loop.nodes.architect_node"]
coder_module = sys.modules["copium_loop.nodes.coder_node"]
reviewer_module = sys.modules["copium_loop.nodes.reviewer_node"]


@pytest.mark.asyncio
async def test_nodes_do_not_call_get_all_memories(agent_state):
    # We want to ensure that nodes don't try to call get_all_memories
    # If we remove it from MemoryManager, calling it will raise AttributeError.

    agent_state["messages"] = [HumanMessage(content="test")]
    agent_state["initial_commit_hash"] = "abc"
    agent_state["test_output"] = "PASS"

    agent_state["engine"].invoke.return_value = "Done"
    await coder(agent_state)
    # We don't want "## Global Persona Memory" or similar in the prompt
    # because it should be autoloaded by gemini-cli, not manually added by us.
    prompt = agent_state["engine"].invoke.call_args[0][0]
    assert "## Global Persona Memory" not in prompt
    assert "## Project-Specific Memory" not in prompt

    agent_state["engine"].invoke.reset_mock()
    with patch(
        "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
    ) as mock_arch_diff:
        mock_arch_diff.return_value = "diff"
        agent_state["engine"].invoke.return_value = "VERDICT: OK"
        await architect(agent_state)
        prompt = agent_state["engine"].invoke.call_args[0][0]
        assert "## Global Persona Memory" not in prompt
        assert "## Project-Specific Memory" not in prompt

    agent_state["engine"].invoke.reset_mock()
    with patch(
        "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
    ) as mock_rev_diff:
        mock_rev_diff.return_value = "diff"
        agent_state["engine"].invoke.return_value = "VERDICT: APPROVED"
        await reviewer(agent_state)
        prompt = agent_state["engine"].invoke.call_args[0][0]
        assert "## Global Persona Memory" not in prompt
        assert "## Project-Specific Memory" not in prompt


def test_memory_manager_methods_removed():
    manager = MemoryManager()
    assert not hasattr(manager, "get_all_memories")
    assert not hasattr(manager, "get_project_context")
    assert not hasattr(manager, "get_global_context")
