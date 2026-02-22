import sys

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.copium_loop import WorkflowManager
from copium_loop.nodes import coder

# Get the module object explicitly to avoid shadowing issues
coder_module = sys.modules["copium_loop.nodes.coder_node"]


class TestCoderNode:
    """Tests for the coder node."""

    @pytest.mark.asyncio
    async def test_coder_returns_coded_status(self, agent_state):
        """Test that coder node returns coded status."""
        agent_state["messages"] = [HumanMessage(content="Build a login form")]
        agent_state["engine"].invoke.return_value = "Mocked Code Response"

        result = await coder(agent_state)

        assert result["code_status"] == "coded"
        assert "Mocked Code Response" in result["messages"][0].content
        assert agent_state["engine"].invoke.called

    @pytest.mark.asyncio
    async def test_coder_includes_test_failure_in_prompt(self, agent_state):
        """Test that coder includes test failure in prompt."""
        agent_state["engine"].invoke.return_value = "Fixing..."

        agent_state["messages"] = [HumanMessage(content="Fix bug")]
        agent_state["test_output"] = "FAIL: Expected 1 to be 2"

        await coder(agent_state)

        # Check that the prompt contains the test failure
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]
        assert "Your previous implementation failed tests." in prompt
        assert "FAIL: Expected 1 to be 2" in prompt

    @pytest.mark.asyncio
    async def test_coder_logs_prompt_when_verbose(self, agent_state):
        """Test that coder logs system prompt when verbose is True."""
        agent_state["messages"] = [HumanMessage(content="Test prompt")]
        agent_state["verbose"] = True

        await coder(agent_state)

        # Check that engine.invoke was called with verbose=True and label="Coder System"
        _, kwargs = agent_state["engine"].invoke.call_args
        assert kwargs["verbose"] is True
        assert kwargs["label"] == "Coder System"

    @pytest.mark.asyncio
    async def test_coder_handles_pr_failure(self, agent_state):
        """Test that coder node handles PR creation failure."""
        agent_state["engine"].invoke.return_value = "Retrying PR..."

        agent_state["messages"] = [
            HumanMessage(content="Original request"),
            SystemMessage(
                content="Failed to create PR: Git push failed (exit 1): error: failed to push some refs"
            ),
        ]
        agent_state["review_status"] = "pr_failed"

        await coder(agent_state)

        # Check that the prompt contains the PR failure message
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]
        assert "Your previous attempt to create a PR failed." in prompt
        assert "Failed to create PR: Git push failed" in prompt

    @pytest.mark.asyncio
    async def test_coder_handles_needs_commit(self, agent_state):
        """Test that coder node handles needs_commit status."""
        agent_state["engine"].invoke.return_value = "Committing..."

        agent_state["messages"] = [HumanMessage(content="Original request")]
        agent_state["review_status"] = "needs_commit"

        await coder(agent_state)

        # Check that the prompt contains the needs_commit message
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]
        assert "You have uncommitted changes that prevent PR creation." in prompt

    @pytest.mark.asyncio
    async def test_coder_handles_rejected_status(self, agent_state):
        """Test that coder node handles rejected status from reviewer."""
        agent_state["engine"].invoke.return_value = "Fixing rejected code..."

        agent_state["messages"] = [
            HumanMessage(content="Original request"),
            SystemMessage(content="Code is too complex."),
        ]
        agent_state["review_status"] = "rejected"

        await coder(agent_state)

        # Check that the prompt contains the rejection message
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]
        assert "Your previous implementation was rejected by the reviewer." in prompt
        assert "Code is too complex." in prompt

    @pytest.mark.asyncio
    async def test_coder_handles_architect_refactor(self, agent_state):
        """Test that coder node handles refactor status from architect."""
        agent_state["engine"].invoke.return_value = "Refactoring code..."

        agent_state["messages"] = [
            HumanMessage(content="Original request"),
            SystemMessage(content="Architecture needs improvement: file too large."),
        ]
        agent_state["architect_status"] = "refactor"

        await coder(agent_state)

        # Check that the prompt contains the architect feedback
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]
        assert (
            "Your previous implementation was flagged for architectural improvement by the architect."
            in prompt
        )
        assert "Architecture needs improvement: file too large." in prompt

    @pytest.mark.asyncio
    async def test_coder_jules_prompt_includes_force_push(self, agent_state):
        """Test that coder node includes force push instruction when using jules engine."""
        agent_state["engine"].engine_type = "jules"
        agent_state["messages"] = [HumanMessage(content="Test jules prompt")]

        await coder(agent_state)

        # Check that the prompt contains the force push instruction
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]
        assert "You MUST explicitly use 'git push --force'" in prompt

    @pytest.mark.asyncio
    async def test_coder_gemini_prompt_includes_tdd_guide_skill(self, agent_state):
        """Test that coder node includes tdd-guide skill instruction when using gemini engine."""
        agent_state["engine"].engine_type = "gemini"
        agent_state["messages"] = [HumanMessage(content="Test gemini prompt")]

        await coder(agent_state)

        # Check that the prompt contains the tdd-guide skill instruction
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]
        assert "To do this, you MUST activate the 'tdd-guide' skill" in prompt
        assert "1. Write tests FIRST (they should fail initially)" in prompt

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
        assert result.get("review_status") != "rejected"

    @pytest.mark.asyncio
    async def test_coder_node_handles_failed_status_with_unexpected_failure_prompt(
        self, agent_state
    ):
        """
        Test that coder node uses "unexpected failure" prompt when code_status is "failed".
        """
        agent_state["engine"].invoke.return_value = "Retrying after failure..."
        agent_state["messages"] = [
            HumanMessage(content="Original request"),
            SystemMessage(content="Unexpected connection error"),
        ]
        agent_state["code_status"] = "failed"
        agent_state["retry_count"] = 1

        await coder(agent_state)

        # Check that the prompt contains the "unexpected failure" message
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]

        assert "coder encountered an unexpected failure" in prompt.lower()
        assert "unexpected failure" in prompt.lower()
        assert "Unexpected connection error" in prompt
        assert "rejected by the reviewer" not in prompt

    @pytest.mark.asyncio
    async def test_coder_skips_error_block_on_infrastructure_failure(self, agent_state):
        """Test that coder skips the error block if the failure is an infrastructure error."""
        agent_state["engine"].invoke.return_value = "Retrying..."
        agent_state["messages"] = [
            HumanMessage(content="Original request"),
            SystemMessage(content="fatal: unable to access 'https://github.com/...'"),
        ]
        agent_state["code_status"] = "failed"
        agent_state["last_error"] = "fatal: unable to access 'https://github.com/...'"

        await coder(agent_state)

        # Check that the prompt DOES NOT contain the <error> block
        call_args = agent_state["engine"].invoke.call_args[0]
        prompt = call_args[0]
        assert "<error>" not in prompt
        assert "fatal: unable to access" not in prompt
