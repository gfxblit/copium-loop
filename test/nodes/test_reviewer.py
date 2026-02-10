import sys
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes.reviewer import reviewer

# Get the module object explicitly to avoid shadowing issues
reviewer_module = sys.modules["copium_loop.nodes.reviewer"]


class TestReviewerNode:
    """Tests for the reviewer node."""

    @pytest.fixture(autouse=True)
    def setup_reviewer_mocks(self):
        """Setup common mocks for reviewer tests."""
        self.mock_get_diff_patcher = patch.object(
            reviewer_module, "get_diff", new_callable=AsyncMock
        )
        self.mock_get_diff = self.mock_get_diff_patcher.start()
        self.mock_get_diff.return_value = "diff content"

        self.mock_is_git_repo_patcher = patch.object(
            reviewer_module, "is_git_repo", new_callable=AsyncMock
        )
        self.mock_is_git_repo = self.mock_is_git_repo_patcher.start()
        self.mock_is_git_repo.return_value = True

        yield

        self.mock_get_diff_patcher.stop()
        self.mock_is_git_repo_patcher.stop()

    @pytest.mark.asyncio
    async def test_reviewer_returns_approved(self):
        """Test that reviewer returns approved status."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: APPROVED"

            state = {"test_output": "PASS", "retry_count": 0, "initial_commit_hash": "abc"}
            result = await reviewer(state)

            assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_returns_rejected(self):
        """Test that reviewer returns rejected status."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: REJECTED\nissues"

            state = {"test_output": "PASS", "retry_count": 0, "initial_commit_hash": "abc"}
            result = await reviewer(state)

            assert result["review_status"] == "rejected"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_takes_last_verdict(self):
        """Test that reviewer takes the last verdict found in the content."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = (
                "VERDICT: REJECTED\nWait, I changed my mind.\nVERDICT: APPROVED"
            )

            state = {"test_output": "PASS", "retry_count": 0, "initial_commit_hash": "abc"}
            result = await reviewer(state)

            assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_rejects_on_test_failure(self):
        """Test that reviewer rejects when tests fail."""
        state = {"test_output": "FAIL", "retry_count": 0}
        result = await reviewer(state)

        assert result["review_status"] == "rejected"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_allows_empty_test_output(self):
        """Test that reviewer proceeds with empty test output."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "Thinking...\nVERDICT: APPROVED"

            state = {"test_output": "", "retry_count": 0, "initial_commit_hash": "abc"}
            result = await reviewer(state)

            assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_returns_error_on_exception(self):
        """Test that reviewer returns error status on exception."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.side_effect = Exception("API Error")

            state = {"test_output": "PASS", "retry_count": 0, "initial_commit_hash": "abc"}
            result = await reviewer(state)

            assert result["review_status"] == "error"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_returns_error_on_missing_verdict(self):
        """Test that reviewer returns error status when no verdict is found."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "I am not sure what to do."

            state = {"test_output": "PASS", "retry_count": 0, "initial_commit_hash": "abc"}
            result = await reviewer(state)

            assert result["review_status"] == "error"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_no_notification_on_rejected(self):
        """Test that reviewer does not send notification on rejection."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: REJECTED"

            state = {"test_output": "PASS", "retry_count": 0, "initial_commit_hash": "abc"}
            result = await reviewer(state)

            assert result["review_status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reviewer_false_rejection_repro(self):
        """Test that reviewer does not falsely reject on options string."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            # This simulates the failure reported in issue #20
            mock_gemini.return_value = "I cannot determine the final status (APPROVED/REJECTED). I hit a quota limit."

            state = {"test_output": "PASS", "retry_count": 0, "initial_commit_hash": "abc"}
            result = await reviewer(state)

            # Expected: it should be "error" because no REAL verdict was given
            assert result["review_status"] == "error"

    @pytest.mark.asyncio
    @patch.object(reviewer_module, "get_diff", new_callable=AsyncMock)
    async def test_reviewer_handles_git_diff_failure(self, mock_get_diff):
        """Test that reviewer handles failure to get git diff."""
        mock_get_diff.side_effect = Exception("git diff error")

        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: APPROVED"

            state = {
                "test_output": "PASS",
                "retry_count": 0,
                "initial_commit_hash": "abc",
            }
            result = await reviewer(state)

            assert result["review_status"] == "approved"
            mock_get_diff.assert_called_once()

    @pytest.mark.asyncio
    async def test_reviewer_skips_llm_on_empty_diff(self):
        """Test that reviewer returns approved immediately if git diff is empty, without invoking LLM."""
        with patch.object(
            reviewer_module, "get_diff", new_callable=AsyncMock
        ) as mock_get_diff:
            mock_get_diff.return_value = ""  # Force empty diff
            
            with patch.object(
                reviewer_module, "invoke_gemini", new_callable=AsyncMock
            ) as mock_gemini:
                mock_gemini.return_value = "VERDICT: APPROVED"

                state = {
                    "test_output": "PASS",
                    "initial_commit_hash": "some_hash",
                    "retry_count": 0,
                    "verbose": False,
                }

                # Run reviewer node
                result = await reviewer(state)

                # Verify
                mock_get_diff.assert_called_once()
                mock_gemini.assert_not_called()
                assert result["review_status"] == "approved"
                assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_reviewer_prompt_contains_example(self):
        """Test that the reviewer system prompt contains an example block."""
        with patch.object(
            reviewer_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: APPROVED"

            state = {"test_output": "PASS", "retry_count": 0, "initial_commit_hash": "abc"}
            await reviewer(state)

            args, kwargs = mock_gemini.call_args
            system_prompt = args[0]
            assert "EXAMPLE:" in system_prompt
            assert system_prompt.count("VERDICT: APPROVED") == 2
            assert system_prompt.count("VERDICT: REJECTED") == 2
