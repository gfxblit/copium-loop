import sys
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import tester

# Get the module object explicitly to avoid shadowing issues
tester_module = sys.modules["copium_loop.nodes.tester_node"]


class TestTesterNode:
    """Tests for the test runner node."""

    @pytest.mark.asyncio
    async def test_tester_returns_pass_with_build(self, agent_state):
        """Test that test runner returns PASS when build, lint and tests pass."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(
                tester_module,
                "get_build_command",
                return_value=("npm", ["run", "build"]),
            ),
        ):
            # 1. Lint, 2. Build, 3. Unit Tests
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "Build passed", "exit_code": 0},
                {"output": "All tests passed", "exit_code": 0},
            ]

            agent_state["retry_count"] = 0
            result = await tester(agent_state)

            assert result["test_output"] == "PASS"
            assert mock_run.call_count == 3

    @pytest.mark.asyncio
    async def test_tester_returns_fail_on_lint(self, agent_state):
        """Test that test runner returns FAIL if linting fails."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(tester_module, "get_telemetry") as mock_get_telemetry,
        ):
            mock_log_status = mock_get_telemetry.return_value.log_status
            mock_run.return_value = {"output": "Linting failed", "exit_code": 1}
            agent_state["retry_count"] = 0
            result = await tester(agent_state)

            assert "FAIL (Lint)" in result["test_output"]
            assert result["retry_count"] == 1
            # Should NOT call build or unit tests if lint fails
            assert mock_run.call_count == 1
            mock_log_status.assert_any_call("tester", "failed")

    @pytest.mark.asyncio
    async def test_tester_returns_fail_on_build(self, agent_state):
        """Test that test runner returns FAIL if build fails."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(
                tester_module,
                "get_build_command",
                return_value=("npm", ["run", "build"]),
            ),
            patch.object(tester_module, "get_telemetry") as mock_get_telemetry,
        ):
            mock_log_status = mock_get_telemetry.return_value.log_status
            # 1. Lint passes, 2. Build fails
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "Build failed", "exit_code": 1},
            ]
            agent_state["retry_count"] = 0
            result = await tester(agent_state)

            assert "FAIL (Build)" in result["test_output"]
            assert result["retry_count"] == 1
            # Should NOT call unit tests if build fails
            assert mock_run.call_count == 2
            mock_log_status.assert_any_call("tester", "failed")

    @pytest.mark.asyncio
    async def test_tester_returns_fail_on_test(self, agent_state):
        """Test that test runner returns FAIL if unit tests fail."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(
                tester_module,
                "get_build_command",
                return_value=("npm", ["run", "build"]),
            ),
            patch.object(tester_module, "get_telemetry") as mock_get_telemetry,
        ):
            mock_log_status = mock_get_telemetry.return_value.log_status
            # 1. Lint passes, 2. Build passes, 3. Test fails
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "Build passed", "exit_code": 0},
                {"output": "FAIL tests", "exit_code": 1},
            ]
            agent_state["retry_count"] = 0
            result = await tester(agent_state)

            assert "FAIL (Unit)" in result["test_output"]
            assert result["retry_count"] == 1
            assert mock_run.call_count == 3
            mock_log_status.assert_any_call("tester", "failed")

    @pytest.mark.asyncio
    async def test_tester_false_positive_avoidance(self, agent_state):
        """Test that '0 failed' or 'failed' in test names don't trigger failure with exit code 0."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(
                tester_module,
                "get_build_command",
                return_value=("", []),
            ),
        ):
            # 1. Lint passes, 2. Test output contains '0 failed' but exit 0
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "Tests: 10 passed, 0 failed", "exit_code": 0},
            ]
            agent_state["retry_count"] = 0
            result = await tester(agent_state)
            assert result["test_output"] == "PASS"

            # 3. Lint passes, 4. Test output contains 'failed' in name but exit 0
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "PASS test_failed_logic.ts", "exit_code": 0},
            ]
            agent_state["retry_count"] = 0
            result = await tester(agent_state)
            assert result["test_output"] == "PASS"

    @pytest.mark.asyncio
    async def test_tester_detects_lint_failure_with_exit_0(self, agent_state):
        """Test that tester node detects lint failures even if exit code is 0."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(tester_module, "get_telemetry") as mock_get_telemetry,
        ):
            mock_log_status = mock_get_telemetry.return_value.log_status
            # Linting prints "error:" but exits with 0
            mock_run.return_value = {
                "output": "ruff check found error: unreachable code",
                "exit_code": 0,
            }
            agent_state["retry_count"] = 0
            result = await tester(agent_state)

            assert "FAIL (Lint)" in result["test_output"]
            assert result["retry_count"] == 1
            mock_log_status.assert_any_call("tester", "failed")

    @pytest.mark.asyncio
    async def test_tester_still_detects_failure_with_exit_0(self, agent_state):
        """Test that explicit failure indicators still trigger failure even if exit code is 0."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(
                tester_module,
                "get_build_command",
                return_value=("", []),
            ),
        ):
            # 1. Lint passes, 2. Test output contains '1 failed'
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "Tests: 9 passed, 1 failed", "exit_code": 0},
                {"output": "Linting passed", "exit_code": 0},
                {"output": "FAILED test_file.py", "exit_code": 0},
            ]
            agent_state["retry_count"] = 0
            result = await tester(agent_state)
            assert "FAIL (Unit)" in result["test_output"]

            agent_state["retry_count"] = 0
            result = await tester(agent_state)
            assert "FAIL (Unit)" in result["test_output"]

    @pytest.mark.asyncio
    async def test_tester_returns_fail_on_coverage_pytest(self, agent_state):
        """Test that test runner returns FAIL (Coverage) if pytest coverage is low."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(
                tester_module,
                "get_build_command",
                return_value=("", []),
            ),
            patch.object(tester_module, "get_telemetry") as mock_get_telemetry,
        ):
            mock_log_status = mock_get_telemetry.return_value.log_status
            # 1. Lint passes, 2. Unit tests fail due to coverage
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {
                    "output": "Required test coverage of 80% not reached. Total coverage: 75.0%",
                    "exit_code": 1,
                },
            ]
            agent_state["retry_count"] = 0
            result = await tester(agent_state)

            assert "FAIL (Coverage)" in result["test_output"]
            assert "Total coverage: 75.0%" in result["test_output"]
            assert result["retry_count"] == 1
            mock_log_status.assert_any_call("tester", "failed")

    @pytest.mark.asyncio
    async def test_tester_returns_fail_on_coverage_jest(self, agent_state):
        """Test that test runner returns FAIL (Coverage) if Jest coverage is low."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(
                tester_module,
                "get_build_command",
                return_value=("", []),
            ),
            patch.object(tester_module, "get_telemetry") as mock_get_telemetry,
        ):
            mock_log_status = mock_get_telemetry.return_value.log_status
            # 1. Lint passes, 2. Unit tests fail due to coverage
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {
                    "output": "Jest: Coverage for lines (75%) does not meet global threshold (80%)",
                    "exit_code": 1,
                },
            ]
            agent_state["retry_count"] = 0
            result = await tester(agent_state)

            assert "FAIL (Coverage)" in result["test_output"]
            assert "Jest: Coverage for lines (75%)" in result["test_output"]
            mock_log_status.assert_any_call("tester", "failed")

    @pytest.mark.asyncio
    async def test_tester_returns_fail_on_coverage_nyc(self, agent_state):
        """Test that test runner returns FAIL (Coverage) if nyc/c8 coverage is low."""
        with (
            patch.object(
                tester_module, "run_command", new_callable=AsyncMock
            ) as mock_run,
            patch.object(
                tester_module,
                "get_build_command",
                return_value=("", []),
            ),
            patch.object(tester_module, "get_telemetry") as mock_get_telemetry,
        ):
            mock_log_status = mock_get_telemetry.return_value.log_status
            # 1. Lint passes, 2. Unit tests fail due to coverage
            mock_run.side_effect = [
                {"output": "Linting passed", "exit_code": 0},
                {"output": "Coverage check failed", "exit_code": 1},
            ]
            agent_state["retry_count"] = 0
            result = await tester(agent_state)

            assert "FAIL (Coverage)" in result["test_output"]
            mock_log_status.assert_any_call("tester", "failed")
