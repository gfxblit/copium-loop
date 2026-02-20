from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.memory import MemoryManager
from copium_loop.nodes import architect, coder, reviewer


def test_log_learning(tmp_path):
    # Use a temporary directory as the project root
    manager = MemoryManager(project_root=tmp_path)
    fact = "Always check for null pointers."
    manager.log_learning(fact)

    memory_file = tmp_path / "GEMINI.md"
    assert memory_file.exists()
    content = memory_file.read_text()
    assert fact in content
    assert "[20" in content  # Basic check for a year in timestamp


def test_get_project_memories(tmp_path):
    manager = MemoryManager(project_root=tmp_path)
    memory_file = tmp_path / "GEMINI.md"
    memory_file.write_text(
        "- [2026-01-31 18:02:11] Fact 1\n- [2026-01-31 18:09:36] Fact 2\n"
    )

    memories = manager.get_project_memories()
    assert memories == ["Fact 1", "Fact 2"]


def test_get_project_memories_empty(tmp_path):
    manager = MemoryManager(project_root=tmp_path)
    assert manager.get_project_memories() == []


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
