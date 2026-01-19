from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.nodes import coder


class TestCoderNode:
    """Tests for the coder node."""

    @pytest.mark.asyncio
    async def test_coder_returns_coded_status(self):
        """Test that coder node returns coded status."""
        with patch(
            "copium_loop.nodes.coder.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "Mocked Code Response"

            state = {"messages": [HumanMessage(content="Build a login form")]}
            result = await coder(state)

            assert result["code_status"] == "coded"
            assert "Mocked Code Response" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_coder_includes_test_failure_in_prompt(self):
        """Test that coder includes test failure in prompt."""
        with patch(
            "copium_loop.nodes.coder.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "Fixing..."

            state = {
                "messages": [HumanMessage(content="Fix bug")],
                "test_output": "FAIL: Expected 1 to be 2",
            }
            await coder(state)

            # Check that the prompt contains the test failure
            call_args = mock_gemini.call_args[0]
            prompt = call_args[0]
            assert "Your previous implementation failed tests." in prompt
            assert "FAIL: Expected 1 to be 2" in prompt

    @pytest.mark.asyncio
    async def test_coder_logs_prompt_when_verbose(self):
        """Test that coder logs system prompt when verbose is True."""
        with patch(
            "copium_loop.nodes.coder.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "Response"

            state = {"messages": [HumanMessage(content="Test prompt")], "verbose": True}
            await coder(state)

            # Check that invoke_gemini was called with verbose=True and label="Coder System"
            _, kwargs = mock_gemini.call_args
            assert kwargs["verbose"] is True
            assert kwargs["label"] == "Coder System"

    @pytest.mark.asyncio
    async def test_coder_handles_pr_failure(self):
        """Test that coder node handles PR creation failure."""
        with patch(
            "copium_loop.nodes.coder.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "Retrying PR..."

            state = {
                "messages": [
                    HumanMessage(content="Original request"),
                    SystemMessage(
                        content="Failed to create PR: Git push failed (exit 1): error: failed to push some refs"
                    ),
                ],
                "review_status": "pr_failed",
            }
            await coder(state)

            # Check that the prompt contains the PR failure message
            call_args = mock_gemini.call_args[0]
            prompt = call_args[0]
            assert "Your previous attempt to create a PR failed." in prompt
            assert "Failed to create PR: Git push failed" in prompt
