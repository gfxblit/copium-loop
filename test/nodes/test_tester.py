from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import tester


class TestTesterNode:
    """Tests for the test runner node."""

    @pytest.mark.asyncio
    async def test_tester_returns_pass(self):
        """Test that test runner returns PASS on success (lint and test)."""
        with patch(
            "copium_loop.nodes.tester.run_command", new_callable=AsyncMock
        ) as mock_run:
            # First call for lint, second for unit tests
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "All tests passed", "exit_code": 0},
            ]

            state = {"retry_count": 0}
            result = await tester(state)

            assert result["test_output"] == "PASS"
            assert mock_run.call_count == 2

    @pytest.mark.asyncio
    async def test_tester_returns_fail_on_lint(self):
        """Test that test runner returns FAIL if linting fails."""
        with patch(
            "copium_loop.nodes.tester.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = {"output": "Linting failed", "exit_code": 1}
            state = {"retry_count": 0}
            result = await tester(state)

            assert "FAIL (Lint)" in result["test_output"]
            assert result["retry_count"] == 1
            # Should NOT call unit tests if lint fails
            assert mock_run.call_count == 1

    @pytest.mark.asyncio
    async def test_tester_returns_fail_on_test(self):
        """Test that test runner returns FAIL if unit tests fail."""
        with (
            patch(
                "copium_loop.nodes.tester.run_command", new_callable=AsyncMock
            ) as mock_run,
            patch("copium_loop.nodes.tester.notify", new_callable=AsyncMock),
        ):
            # First call (lint) passes, second call (test) fails
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "FAIL tests", "exit_code": 1},
            ]
            state = {"retry_count": 0}
            result = await tester(state)

            assert "FAIL (Unit)" in result["test_output"]
            assert result["retry_count"] == 1
            assert mock_run.call_count == 2
