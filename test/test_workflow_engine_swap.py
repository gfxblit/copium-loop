from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.copium_loop import WorkflowManager
from copium_loop.engine.gemini import GeminiEngine
from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_engine_hot_swap_on_continue():
    """
    Test that providing --engine on CLI overrides the engine in reconstructed state
    when using --continue.
    """
    # 1. Setup mocks
    with (
        patch("copium_loop.copium_loop.get_telemetry"),
        patch("copium_loop.copium_loop.is_git_repo", return_value=True),
        patch("copium_loop.copium_loop.get_head", return_value="hash123"),
        patch("copium_loop.copium_loop.get_test_command", return_value=("pytest", [])),
        patch("copium_loop.copium_loop.run_command", new_callable=AsyncMock) as mock_run_cmd,
        patch("copium_loop.copium_loop.create_graph") as mock_create_graph,
    ):
        mock_run_cmd.return_value = {"exit_code": 0, "output": "success"}

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"status": "success"}
        mock_create_graph.return_value = mock_graph

        manager = WorkflowManager(start_node="coder")

        # Initial state has GeminiEngine
        reconstructed_state = {
            "engine": GeminiEngine(),
            "retry_count": 1,
        }

        # New engine from CLI is JulesEngine
        new_engine = JulesEngine()

        # We need to mock verify_environment as well or provide what it needs
        with patch.object(manager, "verify_environment", return_value=True):
            await manager.run("test prompt", initial_state=reconstructed_state, engine=new_engine)

            # Verify that ainvoke was called with the NEW engine
            called_state = mock_graph.ainvoke.call_args[0][0]
            assert isinstance(called_state["engine"], JulesEngine)
            assert called_state["retry_count"] == 1

@pytest.mark.asyncio
async def test_engine_persists_on_continue_if_not_overridden():
    """
    Test that the engine from reconstructed state is used if no engine is provided on CLI.
    """
    # 1. Setup mocks
    with (
        patch("copium_loop.copium_loop.get_telemetry"),
        patch("copium_loop.copium_loop.is_git_repo", return_value=True),
        patch("copium_loop.copium_loop.get_head", return_value="hash123"),
        patch("copium_loop.copium_loop.get_test_command", return_value=("pytest", [])),
        patch("copium_loop.copium_loop.run_command", new_callable=AsyncMock) as mock_run_cmd,
        patch("copium_loop.copium_loop.create_graph") as mock_create_graph,
    ):
        mock_run_cmd.return_value = {"exit_code": 0, "output": "success"}

        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = {"status": "success"}
        mock_create_graph.return_value = mock_graph

        manager = WorkflowManager(start_node="coder")

        # Initial state has JulesEngine (maybe it was set in a previous run)
        reconstructed_state = {
            "engine": JulesEngine(),
            "retry_count": 1,
        }

        with patch.object(manager, "verify_environment", return_value=True):
            # No engine provided on CLI
            await manager.run("test prompt", initial_state=reconstructed_state, engine=None)

            # Verify that ainvoke was called with the engine from state (JulesEngine)
            called_state = mock_graph.ainvoke.call_args[0][0]
            assert isinstance(called_state["engine"], JulesEngine)
