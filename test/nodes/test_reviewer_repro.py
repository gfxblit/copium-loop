from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes.reviewer import reviewer


@pytest.mark.asyncio
async def test_reviewer_false_rejection_repro():
    """Test that reviewer does not falsely reject on options string."""
    with patch(
        "copium_loop.nodes.reviewer.invoke_gemini", new_callable=AsyncMock
    ) as mock_gemini:
        # This simulates the failure reported in issue #20
        mock_gemini.return_value = "I cannot determine the final status (APPROVED/REJECTED). I hit a quota limit."

        state = {"test_output": "PASS", "retry_count": 0}
        result = await reviewer(state)

        # Expected: it should be "error" because no REAL verdict was given
        # Actual (currently): it will be "rejected" because it finds "REJECTED" in the string
        assert result["review_status"] == "error"
