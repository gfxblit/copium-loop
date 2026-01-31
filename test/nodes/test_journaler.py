from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes.journaler import journaler
from copium_loop.state import AgentState


@pytest.mark.asyncio
async def test_journaler_success():
    state: AgentState = {
        "messages": [],
        "code_status": "coded",
        "test_output": "All tests passed",
        "review_status": "approved",
        "architect_status": "",
        "retry_count": 0,
        "pr_url": "http://github.com/pr/1",
        "issue_url": "http://github.com/issue/37",
        "initial_commit_hash": "abc",
        "git_diff": "diff content",
        "verbose": False,
        "last_error": ""
    }

    with patch("copium_loop.nodes.journaler.invoke_gemini", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "Always ensure memory is persisted."

        with patch("copium_loop.nodes.journaler.MemoryManager") as mock_memory_manager:
            instance = mock_memory_manager.return_value

            result = await journaler(state)

            assert result["journal_status"] == "journaled"
            instance.log_learning.assert_called_once_with("Always ensure memory is persisted.")
            mock_invoke.assert_called_once()
            # Verify that the prompt contains some relevant info
            args, kwargs = mock_invoke.call_args
            prompt = args[0]
            assert "diff content" in prompt
            assert "All tests passed" in prompt
