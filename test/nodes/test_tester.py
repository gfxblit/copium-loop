from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import tester


class TestTesterNode:
    """Tests for the test runner node."""

    @pytest.mark.asyncio
    async def test_tester_returns_pass(self):
        """Test that test runner returns PASS on success."""
        with patch(
            "copium_loop.nodes.tester.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = {"output": "All tests passed", "exit_code": 0}

            state = {"retry_count": 0}
            result = await tester(state)

            assert result["test_output"] == "PASS"

    @pytest.mark.asyncio
    async def test_tester_returns_fail(self):
        """Test that test runner returns FAIL on failure."""
        with (
            patch(
                "copium_loop.nodes.tester.run_command", new_callable=AsyncMock
            ) as mock_run,
            patch("copium_loop.nodes.tester.notify", new_callable=AsyncMock),
        ):
            mock_run.return_value = {"output": "FAIL tests", "exit_code": 1}
            state = {"retry_count": 0}
            result = await tester(state)

            assert "FAIL" in result["test_output"]
            assert result["retry_count"] == 1
