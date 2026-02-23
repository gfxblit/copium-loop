import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.__main__ import async_main


def test_cli_invalid_start_node():
    """
    Test that the CLI fails with a non-zero exit code and prints an error message
    when an invalid start node is provided.
    """
    # Run the CLI command
    env = {"PYTHONPATH": "src"}
    result = subprocess.run(
        [sys.executable, "-m", "copium_loop", "-n", "invalid_node", "test prompt"],
        capture_output=True,
        text=True,
        env=env,
    )

    # Check exit code
    assert result.returncode != 0, (
        f"Expected non-zero exit code, got {result.returncode}"
    )

    # Check stderr for error message
    # Note: The exact error message might change during implementation, but it should contain "invalid start node"
    assert (
        "Invalid start node" in result.stdout or "Invalid start node" in result.stderr
    )
    assert "Valid nodes are:" in result.stdout or "Valid nodes are:" in result.stderr


def test_readme_mentions_monitor_flag():
    """Verify README mentions the --monitor flag."""
    with open("README.md") as f:
        content = f.read()
    assert "--monitor" in content or "-m " in content or " -m" in content


def test_readme_mentions_continue_flag():
    """Verify README mentions the --continue flag."""
    with open("README.md") as f:
        content = f.read()
    assert "--continue" in content or " -c" in content


def test_readme_mentions_node_flag():
    """Verify README mentions the --node flag."""
    with open("README.md") as f:
        content = f.read()
    assert "--node" in content or " -n" in content


def test_readme_mentions_python_support():
    """Verify README mentions Python/pytest support in 'How It Works' or 'Usage'."""
    with open("README.md") as f:
        content = f.read()
    # Check if it mentions pytest in the context of automatic detection
    assert "pytest" in content.lower() and "detect" in content.lower()


def test_readme_mentions_custom_commands():
    """Verify README mentions custom command environment variables."""
    with open("README.md") as f:
        content = f.read()
    assert "COPIUM_TEST_CMD" in content or "custom commands" in content.lower()


def test_readme_mentions_issue_linking():
    """Verify README mentions automatic GitHub issue linking."""
    with open("README.md") as f:
        content = f.read()
    assert "issue" in content.lower() and (
        "link" in content.lower() or "refer" in content.lower()
    )


def test_readme_mentions_dashboard():
    """Verify README mentions the multi-session monitor/dashboard."""
    with open("README.md") as f:
        content = f.read()
    assert "monitor" in content.lower() or "dashboard" in content.lower()


@pytest.mark.asyncio
class TestMainTelemetry:
    """Tests for telemetry logging in __main__.py."""

    @patch("copium_loop.copium_loop.WorkflowManager")
    @patch("copium_loop.telemetry.get_telemetry")
    @patch("argparse.ArgumentParser.parse_args")
    async def test_async_main_logs_failure_on_non_convergent_exit(
        self, mock_parse_args, mock_get_telemetry, mock_workflow_manager
    ):
        # Setup mocks
        mock_args = MagicMock()
        mock_args.monitor = False
        mock_args.continue_session = False
        mock_args.prompt = ["test", "prompt"]
        mock_args.node = "coder"
        mock_args.verbose = True
        mock_args.engine = "gemini"
        mock_parse_args.return_value = mock_args

        mock_telemetry = MagicMock()
        mock_get_telemetry.return_value = mock_telemetry

        mock_workflow = AsyncMock()
        # Return a non-convergent result
        mock_workflow.run.return_value = {"review_status": "rejected"}
        mock_workflow_manager.return_value = mock_workflow

        # We expect sys.exit(1) to be called
        with patch("sys.exit") as mock_exit:
            await async_main()
            mock_exit.assert_called_with(1)
            # Verify log_workflow_status("failed") was called
            mock_telemetry.log_workflow_status.assert_called_with("failed")

    @patch("copium_loop.copium_loop.WorkflowManager")
    @patch("copium_loop.telemetry.get_telemetry")
    @patch("argparse.ArgumentParser.parse_args")
    async def test_async_main_logs_failure_on_exception(
        self, mock_parse_args, mock_get_telemetry, mock_workflow_manager
    ):
        # Setup mocks
        mock_args = MagicMock()
        mock_args.monitor = False
        mock_args.continue_session = False
        mock_args.prompt = ["test", "prompt"]
        mock_args.node = "coder"
        mock_args.verbose = True
        mock_args.engine = "gemini"
        mock_parse_args.return_value = mock_args

        mock_telemetry = MagicMock()
        mock_get_telemetry.return_value = mock_telemetry

        mock_workflow = AsyncMock()
        mock_workflow.run.side_effect = Exception("test error")
        mock_workflow_manager.return_value = mock_workflow

        # We expect sys.exit(1) to be called
        with patch("sys.exit") as mock_exit:
            await async_main()
            mock_exit.assert_called_with(1)
            # Verify log_workflow_status("failed") was called
            mock_telemetry.log_workflow_status.assert_called_with("failed")
