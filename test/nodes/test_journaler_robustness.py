import sys
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes.journaler import journaler
from copium_loop.state import AgentState

# Get the module object explicitly to avoid shadowing issues
journaler_module = sys.modules["copium_loop.nodes.journaler"]


@pytest.mark.asyncio
async def test_journaler_handles_invoke_gemini_exception_gracefully():
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

    # Simulate an exception in invoke_gemini
    with patch.object(
        journaler_module, "invoke_gemini", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.side_effect = Exception("Gemini service unavailable")

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
async def test_journaler_handles_memory_manager_exception_gracefully():
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

    with patch.object(
        journaler_module, "invoke_gemini", new_callable=AsyncMock
    ) as mock_invoke:
        mock_invoke.return_value = "Critical Lesson"

        # Simulate exception in MemoryManager
        with patch.object(
            journaler_module, "MemoryManager"
        ) as MockMemoryManager:
            mock_instance = MockMemoryManager.return_value
            mock_instance.log_learning.side_effect = Exception("Disk full")

            result = await journaler(state)

            assert result["journal_status"] == "failed"
            assert result["review_status"] == "journaled"
