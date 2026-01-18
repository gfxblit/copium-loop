import pytest
from unittest.mock import AsyncMock, patch
from copium_loop.nodes import reviewer

class TestReviewerNode:
    """Tests for the reviewer node."""

    @pytest.mark.asyncio
    async def test_reviewer_returns_approved(self):
        """Test that reviewer returns approved status."""
        with patch('copium_loop.nodes.reviewer.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'APPROVED'

            state = {'test_output': 'PASS', 'retry_count': 0}
            result = await reviewer(state)

            assert result['review_status'] == 'approved'

    @pytest.mark.asyncio
    async def test_reviewer_returns_rejected(self):
        """Test that reviewer returns rejected status."""
        with patch('copium_loop.nodes.reviewer.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'REJECTED: issues'

            state = {'test_output': 'PASS', 'retry_count': 0}
            result = await reviewer(state)

            assert result['review_status'] == 'rejected'
            assert result['retry_count'] == 1

    @pytest.mark.asyncio
    async def test_reviewer_rejects_on_test_failure(self):
        """Test that reviewer rejects when tests fail."""
        state = {'test_output': 'FAIL', 'retry_count': 0}
        result = await reviewer(state)

        assert result['review_status'] == 'rejected'
        assert result['retry_count'] == 1

    @pytest.mark.asyncio
    async def test_reviewer_allows_empty_test_output(self):
        """Test that reviewer proceeds with empty test output."""
        with patch('copium_loop.nodes.reviewer.invoke_gemini', new_callable=AsyncMock) as mock_gemini:
            mock_gemini.return_value = 'Thinking...\nAPPROVED'

            state = {'test_output': '', 'retry_count': 0}
            result = await reviewer(state)

            assert result['review_status'] == 'approved'
