from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.memory import MemoryManager
from copium_loop.nodes.architect import architect
from copium_loop.nodes.coder import coder
from copium_loop.nodes.reviewer import reviewer


@pytest.mark.asyncio
async def test_nodes_do_not_call_get_all_memories():
    # We want to ensure that nodes don't try to call get_all_memories
    # If we remove it from MemoryManager, calling it will raise AttributeError.

    state = {"messages": [HumanMessage(content="test")]}

    with patch(
        "copium_loop.nodes.coder.invoke_gemini", new_callable=AsyncMock
    ) as mock_coder_gemini:
        mock_coder_gemini.return_value = "Done"
        await coder(state)
        # We don't want "## Global Persona Memory" or similar in the prompt
        # because it should be autoloaded by gemini-cli, not manually added by us.
        prompt = mock_coder_gemini.call_args[0][0]
        assert "## Global Persona Memory" not in prompt
        assert "## Project-Specific Memory" not in prompt

    with patch(
        "copium_loop.nodes.architect.invoke_gemini", new_callable=AsyncMock
    ) as mock_arch_gemini:
        mock_arch_gemini.return_value = "VERDICT: OK"
        await architect(state)
        prompt = mock_arch_gemini.call_args[0][0]
        assert "## Global Persona Memory" not in prompt
        assert "## Project-Specific Memory" not in prompt

    with patch(
        "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
    ) as mock_rev_gemini:
        mock_rev_gemini.return_value = "VERDICT: APPROVED"
        await reviewer(state)
        prompt = mock_rev_gemini.call_args[0][0]
        assert "## Global Persona Memory" not in prompt
        assert "## Project-Specific Memory" not in prompt


def test_memory_manager_methods_removed():
    manager = MemoryManager()
    assert not hasattr(manager, "get_all_memories")
    assert not hasattr(manager, "get_project_context")
    assert not hasattr(manager, "get_global_context")
