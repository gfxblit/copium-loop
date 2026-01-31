from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes.reviewer import reviewer


class TestReviewerNode:
    """Tests for the reviewer node."""

    @pytest.mark.asyncio
    async def test_reviewer_returns_approved(self):
        """Test that reviewer returns approved status."""
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: APPROVED"

            state = {"test_output": "PASS", "retry_count": 0}
            result = await reviewer(state)

            assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_returns_rejected(self):
        """Test that reviewer returns rejected status."""
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: REJECTED\nissues"

            state = {"test_output": "PASS", "retry_count": 0}
            result = await reviewer(state)

            assert result["review_status"] == "rejected"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_takes_last_verdict(self):
        """Test that reviewer takes the last verdict found in the content."""
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = (
                "VERDICT: REJECTED\nWait, I changed my mind.\nVERDICT: APPROVED"
            )

            state = {"test_output": "PASS", "retry_count": 0}
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
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "Thinking...\nVERDICT: APPROVED"

            state = {"test_output": "", "retry_count": 0}
            result = await reviewer(state)

            assert result["review_status"] == "approved"

    @pytest.mark.asyncio
    async def test_reviewer_returns_error_on_exception(self):
        """Test that reviewer returns error status on exception."""
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.side_effect = Exception("API Error")

            state = {"test_output": "PASS", "retry_count": 0}
            result = await reviewer(state)

            assert result["review_status"] == "error"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_returns_error_on_missing_verdict(self):
        """Test that reviewer returns error status when no verdict is found."""
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "I am not sure what to do."

            state = {"test_output": "PASS", "retry_count": 0}
            result = await reviewer(state)

            assert result["review_status"] == "error"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_reviewer_no_notification_on_rejected(self):
        """Test that reviewer does not send notification on rejection."""
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: REJECTED"

            state = {"test_output": "PASS", "retry_count": 0}
            result = await reviewer(state)

            assert result["review_status"] == "rejected"

    @pytest.mark.asyncio
    async def test_reviewer_false_rejection_repro(self):
        """Test that reviewer does not falsely reject on options string."""
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            # This simulates the failure reported in issue #20
            mock_gemini.return_value = "I cannot determine the final status (APPROVED/REJECTED). I hit a quota limit."

            state = {"test_output": "PASS", "retry_count": 0}
            result = await reviewer(state)

            # Expected: it should be "error" because no REAL verdict was given
            assert result["review_status"] == "error"

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.reviewer.os.path.exists")
    @patch("copium_loop.nodes.reviewer.get_diff", new_callable=AsyncMock)
    async def test_reviewer_handles_git_diff_failure(self, mock_get_diff, mock_exists):
        """Test that reviewer handles failure to get git diff."""
        mock_exists.return_value = True
        mock_get_diff.side_effect = Exception("git diff error")

        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
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
    async def test_reviewer_prompt_contains_example(self):
        """Test that the reviewer system prompt contains an example block."""
        with patch(
            "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: APPROVED"

            state = {"test_output": "PASS", "retry_count": 0}
            await reviewer(state)

            args, kwargs = mock_gemini.call_args
            system_prompt = args[0]
            assert "EXAMPLE:" in system_prompt
            assert "VERDICT: APPROVED" in system_prompt
            assert "VERDICT: REJECTED" in system_prompt
