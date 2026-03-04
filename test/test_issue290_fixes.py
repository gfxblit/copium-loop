from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.languages.node import NodeStrategy
from copium_loop.languages.python import PythonStrategy
from copium_loop.languages.rust import RustStrategy
from copium_loop.nodes.tester_node import tester_node


def test_node_strategy_absolute_path_match(tmp_path):
    strategy = NodeStrategy()
    (tmp_path / "package.json").touch()
    assert strategy.match(str(tmp_path))


def test_rust_strategy_absolute_path_match(tmp_path):
    strategy = RustStrategy()
    (tmp_path / "Cargo.toml").touch()
    assert strategy.match(str(tmp_path))


def test_python_strategy_absolute_path_match(tmp_path):
    strategy = PythonStrategy()
    (tmp_path / "pyproject.toml").touch()
    assert strategy.match(str(tmp_path))


def test_python_strategy_py_files_absolute_path(tmp_path):
    strategy = PythonStrategy()
    (tmp_path / "app.py").touch()
    assert strategy.match(str(tmp_path))


@pytest.mark.asyncio
async def test_tester_node_skips_lint_if_none(agent_state):
    """Test that tester_node skips linting if get_lint_command() returns None."""
    with (
        patch("copium_loop.nodes.tester_node.get_lint_command", return_value=None),
        patch("copium_loop.nodes.tester_node.get_build_command", return_value=None),
        patch("copium_loop.nodes.tester_node.get_test_command", return_value=None),
        patch(
            "copium_loop.nodes.tester_node.run_command", new_callable=AsyncMock
        ) as mock_run,
        patch("copium_loop.nodes.tester_node.get_telemetry"),
    ):
        result = await tester_node(agent_state)
        # Should succeed if all are None
        assert "FAIL" not in result.get("test_output", "")
        assert mock_run.call_count == 0


@pytest.mark.asyncio
async def test_tester_node_logs_useful_msg_on_lint_failure(agent_state):
    """Test that tester_node logs a useful message when linting fails."""
    from copium_loop.languages import Command

    lint_cmd = Command("npm", ["run", "lint"])
    with (
        patch("copium_loop.nodes.tester_node.get_lint_command", return_value=lint_cmd),
        patch("copium_loop.nodes.tester_node.get_build_command", return_value=None),
        patch("copium_loop.nodes.tester_node.get_test_command", return_value=None),
        patch(
            "copium_loop.nodes.tester_node.run_command", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_run.return_value = {"output": "Missing semicolon", "exit_code": 1}
        result = await tester_node(agent_state)
        assert result["test_output"].startswith("FAIL (Lint):")
        msg = result["messages"][0].content
        assert "npm run lint" in msg
        assert "Missing semicolon" in msg
