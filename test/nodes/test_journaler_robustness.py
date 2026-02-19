import sys
from unittest.mock import patch

import pytest

from copium_loop.nodes import journaler

# Get the module object explicitly to avoid shadowing issues
journaler_module = sys.modules["copium_loop.nodes.journaler_node"]


@pytest.mark.asyncio
async def test_journaler_handles_engine_invoke_exception_gracefully(agent_state):
    agent_state["code_status"] = "coded"
    agent_state["test_output"] = "All tests passed"
    agent_state["review_status"] = "pending"
    agent_state["initial_commit_hash"] = "abc"
    agent_state["git_diff"] = "diff content"

    # Simulate an exception in engine.invoke
    agent_state["engine"].invoke.side_effect = Exception("Gemini service unavailable")

    # The function should NOT raise an exception
    result = await journaler(agent_state)

    # It should return a valid dict, ideally indicating failure or fallback
    assert "journal_status" in result
    assert result["journal_status"] == "failed"
    # And ensure review_status is not lost or is set to a sensible default
    assert (
        result["review_status"] == "journaled"
    )  # or "pending", depending on desired behavior. Let's assume we proceed.


@pytest.mark.asyncio
async def test_journaler_handles_memory_manager_exception_gracefully(agent_state):
    agent_state["code_status"] = "coded"
    agent_state["test_output"] = "All tests passed"
    agent_state["review_status"] = "pending"
    agent_state["initial_commit_hash"] = "abc"
    agent_state["git_diff"] = "diff content"

    agent_state["engine"].invoke.return_value = "Critical Lesson"

    # Simulate exception in MemoryManager
    with patch.object(journaler_module, "MemoryManager") as MockMemoryManager:
        mock_instance = MockMemoryManager.return_value
        mock_instance.log_learning.side_effect = Exception("Disk full")

        result = await journaler(agent_state)

        assert result["journal_status"] == "failed"
        assert result["review_status"] == "journaled"
