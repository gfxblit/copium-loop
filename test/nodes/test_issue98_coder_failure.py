import sys
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.copium_loop import WorkflowManager
from copium_loop.nodes import coder

# Get the module object explicitly to avoid shadowing issues
coder_module = sys.modules["copium_loop.nodes.coder"]


class TestIssue98CoderFailure:
    """Tests for issue #98: coder failure produces wrong message."""

    @pytest.mark.asyncio
    async def test_coder_failure_sets_correct_status(self):
        """

        Test that WorkflowManager._handle_error sets code_status="failed"

        but NOT review_status="rejected" for coder node failures.

        """

        manager = WorkflowManager()

        state = {"retry_count": 0}

        # Call _handle_error for coder node

        result = manager._handle_error(state, "coder", "Unexpected failure")

        assert result["code_status"] == "failed"

        # This is the BUG: currently it sets review_status="rejected"

        assert result.get("review_status") != "rejected"

    @pytest.mark.asyncio
    async def test_coder_node_handles_failed_status_with_unexpected_failure_prompt(
        self,
    ):
        """

        Test that coder node uses "unexpected failure" prompt when code_status is "failed".

        """

        with patch.object(
            coder_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "Retrying after failure..."

            state = {
                "messages": [
                    HumanMessage(content="Original request"),
                    SystemMessage(content="All models exhausted"),
                ],
                "code_status": "failed",
                "retry_count": 1,
            }

            await coder(state)

            # Check that the prompt contains the "unexpected failure" message

            call_args = mock_gemini.call_args[0]

            prompt = call_args[0]

            # This is what we WANT

            assert "coder encountered an unexpected failure" in prompt.lower()

            assert "unexpected failure" in prompt.lower()

            assert "All models exhausted" in prompt

            # This is what we DON'T want

            assert "rejected by the reviewer" not in prompt
