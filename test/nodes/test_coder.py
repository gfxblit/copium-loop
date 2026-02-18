import sys
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.nodes import coder

# Get the module object explicitly to avoid shadowing issues
coder_module = sys.modules["copium_loop.nodes.coder_node"]


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.invoke = AsyncMock(return_value="Mocked Code Response")
    engine.sanitize_for_prompt = MagicMock(side_effect=lambda x, _max_length=12000: x)
    return engine


class TestCoderNode:
    """Tests for the coder node."""

    @pytest.mark.asyncio
    async def test_coder_returns_coded_status(self, mock_engine):
        """Test that coder node returns coded status."""
        state = {
            "messages": [HumanMessage(content="Build a login form")],
        }
        result = await coder(state, mock_engine)

        assert result["code_status"] == "coded"
        assert "Mocked Code Response" in result["messages"][0].content
        assert mock_engine.invoke.called

    @pytest.mark.asyncio
    async def test_coder_includes_test_failure_in_prompt(self, mock_engine):
        """Test that coder includes test failure in prompt."""
        mock_engine.invoke.return_value = "Fixing..."

        state = {
            "messages": [HumanMessage(content="Fix bug")],
            "test_output": "FAIL: Expected 1 to be 2",
        }
        await coder(state, mock_engine)

        # Check that the prompt contains the test failure
        call_args = mock_engine.invoke.call_args[0]
        prompt = call_args[0]
        assert "Your previous implementation failed tests." in prompt
        assert "FAIL: Expected 1 to be 2" in prompt

    @pytest.mark.asyncio
    async def test_coder_logs_prompt_when_verbose(self, mock_engine):
        """Test that coder logs system prompt when verbose is True."""
        state = {
            "messages": [HumanMessage(content="Test prompt")],
            "verbose": True,
        }
        await coder(state, mock_engine)

        # Check that engine.invoke was called with verbose=True and label="Coder System"
        _, kwargs = mock_engine.invoke.call_args
        assert kwargs["verbose"] is True
        assert kwargs["label"] == "Coder System"

    @pytest.mark.asyncio
    async def test_coder_handles_pr_failure(self, mock_engine):
        """Test that coder node handles PR creation failure."""
        mock_engine.invoke.return_value = "Retrying PR..."

        state = {
            "messages": [
                HumanMessage(content="Original request"),
                SystemMessage(
                    content="Failed to create PR: Git push failed (exit 1): error: failed to push some refs"
                ),
            ],
            "review_status": "pr_failed",
        }
        await coder(state, mock_engine)

        # Check that the prompt contains the PR failure message
        call_args = mock_engine.invoke.call_args[0]
        prompt = call_args[0]
        assert "Your previous attempt to create a PR failed." in prompt
        assert "Failed to create PR: Git push failed" in prompt

    @pytest.mark.asyncio
    async def test_coder_handles_needs_commit(self, mock_engine):
        """Test that coder node handles needs_commit status."""
        mock_engine.invoke.return_value = "Committing..."

        state = {
            "messages": [HumanMessage(content="Original request")],
            "review_status": "needs_commit",
        }
        await coder(state, mock_engine)

        # Check that the prompt contains the needs_commit message
        call_args = mock_engine.invoke.call_args[0]
        prompt = call_args[0]
        assert "You have uncommitted changes that prevent PR creation." in prompt

    @pytest.mark.asyncio
    async def test_coder_handles_rejected_status(self, mock_engine):
        """Test that coder node handles rejected status from reviewer."""
        mock_engine.invoke.return_value = "Fixing rejected code..."

        state = {
            "messages": [
                HumanMessage(content="Original request"),
                SystemMessage(content="Code is too complex."),
            ],
            "review_status": "rejected",
        }
        await coder(state, mock_engine)

        # Check that the prompt contains the rejection message
        call_args = mock_engine.invoke.call_args[0]
        prompt = call_args[0]
        assert "Your previous implementation was rejected by the reviewer." in prompt
        assert "Code is too complex." in prompt

    @pytest.mark.asyncio
    async def test_coder_handles_architect_refactor(self, mock_engine):
        """Test that coder node handles refactor status from architect."""
        mock_engine.invoke.return_value = "Refactoring code..."

        state = {
            "messages": [
                HumanMessage(content="Original request"),
                SystemMessage(
                    content="Architecture needs improvement: file too large."
                ),
            ],
            "architect_status": "refactor",
        }
        await coder(state, mock_engine)

        # Check that the prompt contains the architect feedback
        call_args = mock_engine.invoke.call_args[0]
        prompt = call_args[0]
        assert (
            "Your previous implementation was flagged for architectural improvement by the architect."
            in prompt
        )
        assert "Architecture needs improvement: file too large." in prompt

    @pytest.mark.asyncio
    async def test_coder_jules_prompt_includes_force_push(self, mock_engine):
        """Test that coder node includes force push instruction when using jules engine."""
        mock_engine.engine_type = "jules"
        state = {
            "messages": [HumanMessage(content="Test jules prompt")],
        }
        await coder(state, mock_engine)

        # Check that the prompt contains the force push instruction
        call_args = mock_engine.invoke.call_args[0]
        prompt = call_args[0]
        assert "You MUST explicitly use 'git push --force'" in prompt

    @pytest.mark.asyncio
    async def test_coder_gemini_prompt_includes_tdd_guide_skill(self, mock_engine):
        """Test that coder node includes tdd-guide skill instruction when using gemini engine."""
        mock_engine.engine_type = "gemini"
        state = {
            "messages": [HumanMessage(content="Test gemini prompt")],
            "engine": mock_engine,
        }
        await coder(state)

        # Check that the prompt contains the tdd-guide skill instruction
        call_args = mock_engine.invoke.call_args[0]
        prompt = call_args[0]
        assert "To do this, you MUST activate the 'tdd-guide' skill" in prompt
        assert "1. Write tests FIRST (they should fail initially)" in prompt
