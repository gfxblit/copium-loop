from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes.tester_node import tester_node
from copium_loop.state import AgentState


@pytest.mark.asyncio
async def test_tester_node_updates_last_error_on_failure():
    """Verify that tester_node updates last_error on all failure paths."""
    state = AgentState(
        messages=[],
        engine=None,
        retry_count=0,
        test_output="",
    )

    with (
        patch(
            "copium_loop.nodes.tester_node.get_lint_command", return_value=("lint", [])
        ),
        patch(
            "copium_loop.nodes.tester_node._run_stage", new_callable=AsyncMock
        ) as mock_run,
        patch("copium_loop.nodes.tester_node.get_telemetry"),
    ):
        # 1. Lint failure
        mock_run.return_value = (False, "lint error output")
        result = await tester_node(state)
        assert "last_error" in result
        assert "lint error output" in result["last_error"]

        # 2. Build failure
        mock_run.side_effect = [
            (True, "lint success"),
            (False, "build error output"),
        ]
        with (
            patch(
                "copium_loop.nodes.tester_node.get_build_command",
                return_value=("build", []),
            ),
        ):
            result = await tester_node(state)
            assert "last_error" in result
            assert "build error output" in result["last_error"]

        # 3. Test failure
        mock_run.side_effect = [
            (True, "lint success"),
            (True, "build success"),
            (False, "test error output"),
        ]
        with (
            patch(
                "copium_loop.nodes.tester_node.get_build_command",
                return_value=("build", []),
            ),
            patch(
                "copium_loop.nodes.tester_node.get_test_command",
                return_value=("test", []),
            ),
        ):
            result = await tester_node(state)
            assert "last_error" in result
            assert "test error output" in result["last_error"]
