import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.nodes.reviewer import reviewer

# Get the module object explicitly to avoid shadowing issues
reviewer_module = sys.modules["copium_loop.nodes.reviewer"]


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.invoke = AsyncMock(return_value="VERDICT: APPROVED")
    engine.sanitize_for_prompt = MagicMock(side_effect=lambda x, _max_length=12000: x)
    return engine


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
    async def test_reviewer_returns_approved(self, mock_engine):
        """Test that reviewer returns approved status."""
        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_returns_rejected(self, mock_engine):
        """Test that reviewer returns rejected status."""
        mock_engine.invoke.return_value = "VERDICT: REJECTED\nissues"

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        assert result["review_status"] == "rejected"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_takes_last_verdict(self, mock_engine):
        """Test that reviewer takes the last verdict found in the content."""
        mock_engine.invoke.return_value = (
            "VERDICT: REJECTED\nWait, I changed my mind.\nVERDICT: APPROVED"
        )

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_rejects_on_test_failure(self, mock_engine):
        """Test that reviewer rejects when tests fail."""
        state = {"test_output": "FAIL", "retry_count": 0, "engine": mock_engine}
        result = await reviewer(state)

        assert result["review_status"] == "rejected"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_allows_empty_test_output(self, mock_engine):
        """Test that reviewer proceeds with empty test output."""
        mock_engine.invoke.return_value = "Thinking...\nVERDICT: APPROVED"

        state = {
            "test_output": "",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_returns_error_on_exception(self, mock_engine):
        """Test that reviewer returns error status on exception."""
        mock_engine.invoke.side_effect = Exception("API Error")

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        assert result["review_status"] == "error"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_returns_error_on_missing_verdict(self, mock_engine):
        """Test that reviewer returns error status when no verdict is found."""
        mock_engine.invoke.return_value = "I am not sure what to do."

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        assert result["review_status"] == "error"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_no_notification_on_rejected(self, mock_engine):
        """Test that reviewer does not send notification on rejection."""
        mock_engine.invoke.return_value = "VERDICT: REJECTED"

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        assert result["review_status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reviewer_false_rejection_repro(self, mock_engine):
        """Test that reviewer does not falsely reject on options string."""
        # This simulates the failure reported in issue #20
        mock_engine.invoke.return_value = "I cannot determine the final status (APPROVED/REJECTED). I hit a quota limit."

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        # Expected: it should be "error" because no REAL verdict was given
        assert result["review_status"] == "error"

    @pytest.mark.asyncio
    @patch.object(reviewer_module, "get_diff", new_callable=AsyncMock)
    async def test_reviewer_handles_git_diff_failure(self, mock_get_diff, mock_engine):
        """Test that reviewer returns error status on git diff failure."""
        mock_get_diff.side_effect = Exception("git diff error")

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await reviewer(state)

        assert result["review_status"] == "error"
        assert result["retry_count"] == 1
        assert "git diff error" in result["messages"][0].content
        mock_get_diff.assert_called_once()

    @pytest.mark.asyncio
    async def test_reviewer_handles_missing_initial_hash(self, mock_engine):
        """Test that reviewer returns error status on missing initial hash in git repo."""
        with patch.object(
            reviewer_module, "is_git_repo", new_callable=AsyncMock
        ) as mock_is_git:
            mock_is_git.return_value = True
            state = {
                "test_output": "PASS",
                "initial_commit_hash": "",
                "retry_count": 0,
                "verbose": False,
                "engine": mock_engine,
            }

            # Run reviewer node
            result = await reviewer(state)

            # Verify
            assert result["review_status"] == "error"
            assert result["retry_count"] == 1
            assert "Missing initial commit hash" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_reviewer_skips_llm_on_empty_diff(self, mock_engine):
        """Test that reviewer returns approved immediately if git diff is empty, without invoking LLM."""
        with patch.object(
            reviewer_module, "get_diff", new_callable=AsyncMock
        ) as mock_get_diff:
            mock_get_diff.return_value = ""  # Force empty diff

            state = {
                "test_output": "PASS",
                "initial_commit_hash": "some_hash",
                "retry_count": 0,
                "verbose": False,
                "engine": mock_engine,
            }

            # Run reviewer node
            result = await reviewer(state)

            # Verify
            mock_get_diff.assert_called_once()
            mock_engine.invoke.assert_not_called()
            assert result["review_status"] == "approved"
            assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_reviewer_prompt_contains_example(self, mock_engine):
        """Test that the reviewer system prompt contains an example block."""
        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        await reviewer(state)

        args, kwargs = mock_engine.invoke.call_args
        system_prompt = args[0]
        assert "EXAMPLE:" in system_prompt
        assert system_prompt.count("VERDICT: APPROVED") == 2
        assert system_prompt.count("VERDICT: REJECTED") == 2
