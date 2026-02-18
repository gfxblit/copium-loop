import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.memory import MemoryManager
from copium_loop.nodes.architect import architect
from copium_loop.nodes.coder import coder
from copium_loop.nodes.reviewer import reviewer

architect_module = sys.modules["copium_loop.nodes.architect"]
coder_module = sys.modules["copium_loop.nodes.coder"]
reviewer_module = sys.modules["copium_loop.nodes.reviewer"]


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.invoke = AsyncMock(return_value="Done")
    engine.sanitize_for_prompt = MagicMock(side_effect=lambda x, _max_length=12000: x)
    return engine


@pytest.mark.asyncio
async def test_nodes_do_not_call_get_all_memories(mock_engine):
    # We want to ensure that nodes don't try to call get_all_memories
    # If we remove it from MemoryManager, calling it will raise AttributeError.

    state = {
        "messages": [HumanMessage(content="test")],
        "initial_commit_hash": "abc",
        "test_output": "PASS",
        "engine": mock_engine,
    }

    mock_engine.invoke.return_value = "Done"
    await coder(state)
    # We don't want "## Global Persona Memory" or similar in the prompt
    # because it should be autoloaded by gemini-cli, not manually added by us.
    prompt = mock_engine.invoke.call_args[0][0]
    assert "## Global Persona Memory" not in prompt
    assert "## Project-Specific Memory" not in prompt

    mock_engine.invoke.reset_mock()
    with patch(
        "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
    ) as mock_arch_diff:
        mock_arch_diff.return_value = "diff"
        mock_engine.invoke.return_value = "VERDICT: OK"
        await architect(state)
        prompt = mock_engine.invoke.call_args[0][0]
        assert "## Global Persona Memory" not in prompt
        assert "## Project-Specific Memory" not in prompt

    mock_engine.invoke.reset_mock()
    with patch(
        "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
    ) as mock_rev_diff:
        mock_rev_diff.return_value = "diff"
        mock_engine.invoke.return_value = "VERDICT: APPROVED"
        await reviewer(state)
        prompt = mock_engine.invoke.call_args[0][0]
        assert "## Global Persona Memory" not in prompt
        assert "## Project-Specific Memory" not in prompt


def test_memory_manager_methods_removed():
    manager = MemoryManager()
    assert not hasattr(manager, "get_all_memories")
    assert not hasattr(manager, "get_project_context")
    assert not hasattr(manager, "get_global_context")
