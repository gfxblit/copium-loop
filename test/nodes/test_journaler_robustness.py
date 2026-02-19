import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.nodes import journaler
from copium_loop.state import AgentState

# Get the module object explicitly to avoid shadowing issues
journaler_module = sys.modules["copium_loop.nodes.journaler_node"]


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.invoke = AsyncMock(return_value="A lesson")
    engine.sanitize_for_prompt = MagicMock(side_effect=lambda x, _max_length=12000: x)
    return engine


@pytest.mark.asyncio
async def test_journaler_handles_engine_invoke_exception_gracefully(mock_engine):
    state: AgentState = {
        "messages": [],
        "code_status": "coded",
        "test_output": "All tests passed",
        "review_status": "pending",
        "architect_status": "",
        "retry_count": 0,
        "pr_url": "",
        "issue_url": "",
        "initial_commit_hash": "abc",
        "git_diff": "diff content",
        "verbose": False,
        "last_error": "",
    }

    # Simulate an exception in engine.invoke
    mock_engine.invoke.side_effect = Exception("Gemini service unavailable")
    state["engine"] = mock_engine

    # The function should NOT raise an exception
    result = await journaler(state)

    # It should return a valid dict, ideally indicating failure or fallback
    assert "journal_status" in result
    assert result["journal_status"] == "failed"
    # And ensure review_status is not lost or is set to a sensible default
    assert (
        result["review_status"] == "journaled"
    )  # or "pending", depending on desired behavior. Let's assume we proceed.


@pytest.mark.asyncio
async def test_journaler_handles_memory_manager_exception_gracefully(mock_engine):
    state: AgentState = {
        "messages": [],
        "code_status": "coded",
        "test_output": "All tests passed",
        "review_status": "pending",
        "architect_status": "",
        "retry_count": 0,
        "pr_url": "",
        "issue_url": "",
        "initial_commit_hash": "abc",
        "git_diff": "diff content",
        "verbose": False,
        "last_error": "",
    }

    mock_engine.invoke.return_value = "Critical Lesson"
    state["engine"] = mock_engine

    # Simulate exception in MemoryManager
    with patch.object(journaler_module, "MemoryManager") as MockMemoryManager:
        mock_instance = MockMemoryManager.return_value
        mock_instance.log_learning.side_effect = Exception("Disk full")

        result = await journaler(state)

        assert result["journal_status"] == "failed"
        assert result["review_status"] == "journaled"
