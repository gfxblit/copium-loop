from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import reviewer


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
