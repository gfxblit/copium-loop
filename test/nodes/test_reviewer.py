import sys
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import reviewer

# Get the module object explicitly to avoid shadowing issues
reviewer_module = sys.modules["copium_loop.nodes.reviewer_node"]


class TestReviewerNode:
    """Tests for the reviewer node."""

    @pytest.fixture(autouse=True)
    def setup_reviewer_mocks(self):
        """Setup common mocks for reviewer tests."""
        self.mock_get_diff_patcher = patch(
            "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
        )
        self.mock_get_diff = self.mock_get_diff_patcher.start()
        self.mock_get_diff.return_value = "diff content"

        self.mock_is_git_repo_patcher = patch(
            "copium_loop.nodes.utils.is_git_repo", new_callable=AsyncMock
        )
        self.mock_is_git_repo = self.mock_is_git_repo_patcher.start()
        self.mock_is_git_repo.return_value = True

        yield

        self.mock_get_diff_patcher.stop()
        self.mock_is_git_repo_patcher.stop()

    @pytest.mark.asyncio
    async def test_reviewer_returns_approved(self, agent_state):
        """Test that reviewer returns approved status."""
        agent_state["engine"].invoke.return_value = "VERDICT: APPROVED"
        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_returns_rejected(self, agent_state):
        """Test that reviewer returns rejected status."""
        agent_state["engine"].invoke.return_value = "VERDICT: REJECTED\nissues"

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        assert result["review_status"] == "rejected"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_takes_last_verdict(self, agent_state):
        """Test that reviewer takes the last verdict found in the content."""
        agent_state[
            "engine"
        ].invoke.return_value = (
            "VERDICT: REJECTED\nWait, I changed my mind.\nVERDICT: APPROVED"
        )

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_rejects_on_test_failure(self, agent_state):
        """Test that reviewer rejects when tests fail."""
        agent_state["test_output"] = "FAIL"
        result = await reviewer(agent_state)

        assert result["review_status"] == "rejected"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_allows_empty_test_output(self, agent_state):
        """Test that reviewer proceeds with empty test output."""
        agent_state["engine"].invoke.return_value = "Thinking...\nVERDICT: APPROVED"

        agent_state["test_output"] = ""
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_returns_error_on_exception(self, agent_state):
        """Test that reviewer returns error status on exception."""
        agent_state["engine"].invoke.side_effect = Exception("API Error")

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        assert result["review_status"] == "error"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_returns_error_on_missing_verdict(self, agent_state):
        """Test that reviewer returns error status when no verdict is found."""
        agent_state["engine"].invoke.return_value = "I am not sure what to do."

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        assert result["review_status"] == "error"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_no_notification_on_rejected(self, agent_state):
        """Test that reviewer does not send notification on rejection."""
        agent_state["engine"].invoke.return_value = "VERDICT: REJECTED"

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        assert result["review_status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reviewer_false_rejection_repro(self, agent_state):
        """Test that reviewer does not falsely reject on options string."""
        # This simulates the failure reported in issue #20
        agent_state[
            "engine"
        ].invoke.return_value = "I cannot determine the final status (APPROVED/REJECTED). I hit a quota limit."

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        # Expected: it should be "error" because no REAL verdict was given
        assert result["review_status"] == "error"

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.utils.get_diff", new_callable=AsyncMock)
    async def test_reviewer_handles_git_diff_failure(self, mock_get_diff, agent_state):
        """Test that reviewer returns error status on git diff failure."""
        mock_get_diff.side_effect = Exception("git diff error")

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await reviewer(agent_state)

        assert result["review_status"] == "error"
        assert result["retry_count"] == 1
        assert "git diff error" in result["messages"][0].content
        mock_get_diff.assert_called_once()

    @pytest.mark.asyncio
    async def test_reviewer_handles_missing_initial_hash(self, agent_state):
        """Test that reviewer returns error status on missing initial hash in git repo."""
        with patch(
            "copium_loop.nodes.utils.is_git_repo", new_callable=AsyncMock
        ) as mock_is_git:
            mock_is_git.return_value = True
            agent_state["test_output"] = "PASS"
            agent_state["initial_commit_hash"] = ""

            # Run reviewer node
            result = await reviewer(agent_state)

            # Verify
            assert result["review_status"] == "error"
            assert result["retry_count"] == 1
            assert "Missing initial commit hash" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_reviewer_skips_llm_on_empty_diff(self, agent_state):
        """Test that reviewer returns approved immediately if git diff is empty, without invoking LLM."""
        with patch(
            "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
        ) as mock_get_diff:
            mock_get_diff.return_value = ""  # Force empty diff

            agent_state["test_output"] = "PASS"
            agent_state["initial_commit_hash"] = "some_hash"

            # Run reviewer node
            result = await reviewer(agent_state)

            # Verify
            mock_get_diff.assert_called_once()
            agent_state["engine"].invoke.assert_not_called()
            assert result["review_status"] == "approved"
            assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_reviewer_prompt_contains_example(self, agent_state):
        """Test that the reviewer system prompt contains an example block."""
        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        await reviewer(agent_state)

        args, kwargs = agent_state["engine"].invoke.call_args
        system_prompt = args[0]
        assert "EXAMPLE:" in system_prompt
        assert system_prompt.count("VERDICT: APPROVED") == 2
        assert system_prompt.count("VERDICT: REJECTED") == 2

    @pytest.mark.asyncio
    async def test_reviewer_prompt_jules_expert(self, agent_state):
        """Test that the Jules reviewer prompt contains expert instructions."""
        agent_state["engine"].engine_type = "jules"
        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"

        await reviewer(agent_state)

        args, kwargs = agent_state["engine"].invoke.call_args
        system_prompt = args[0]

        assert (
            "Principal Software Engineer and Meticulous Code Review Architect"
            in system_prompt
        )
        assert "Establish context by reading relevant files" in system_prompt
        assert "Prioritize logic over style" in system_prompt
        assert 'DO NOT tell the author to "check"' in system_prompt
        assert "VERDICT: APPROVED" in system_prompt
        assert "VERDICT: REJECTED" in system_prompt
        assert "(Current HEAD:" in system_prompt
        assert "starting from commit abc to HEAD" in system_prompt

    @pytest.mark.asyncio
    async def test_reviewer_implicit_approval(self, agent_state):
        """Test that reviewer recognizes implicit approval signals."""
        agent_state[
            "engine"
        ].invoke.return_value = "All plan steps completed. Ready for submission."
        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"

        result = await reviewer(agent_state)

        assert result["review_status"] == "approved"
        assert "Ready for submission" in result["messages"][0].content
