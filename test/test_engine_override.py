from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.copium_loop import WorkflowManager
from copium_loop.engine.base import LLMEngine


class MockEngine(LLMEngine):
    def __init__(self, name="mock"):
        self.name = name

    @property
    def engine_type(self) -> str:
        return "mock"

    async def invoke(self, prompt, **kwargs):
        _ = prompt, kwargs
        return "mock response"

    def get_required_tools(self):
        return []

    def sanitize_for_prompt(self, text: str) -> str:
        return text


@pytest.mark.asyncio
async def test_engine_priority_cli_overrides_saved():
    """Verify that CLI engine argument overrides saved state engine."""

    # Setup mocks
    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = lambda x: x

    with (
        patch(
            "copium_loop.copium_loop.get_engine",
            side_effect=lambda name: MockEngine(name),
        ),
        patch("copium_loop.copium_loop.create_graph", return_value=mock_graph),
        patch(
            "copium_loop.copium_loop.is_git_repo", new_callable=AsyncMock
        ) as mock_is_git,
        patch(
            "copium_loop.copium_loop.run_command", new_callable=AsyncMock
        ) as mock_run,
        patch("copium_loop.copium_loop.get_test_command", return_value=("echo", [])),
        patch("copium_loop.copium_loop.get_telemetry", return_value=MagicMock()),
    ):
        mock_is_git.return_value = False
        mock_run.return_value = {"exit_code": 0}

        # Case 1: CLI engine provided ("cli-engine")
        mgr = WorkflowManager(engine_name="cli-engine")
        mgr.graph = mock_graph
        mgr.verify_environment = AsyncMock(return_value=True)

        saved_engine = MockEngine("saved-engine")
        initial_state = {"engine": saved_engine, "other_data": "value"}

        result_state = await mgr.run("test prompt", initial_state=initial_state)

        # Expectation: The engine used should be "cli-engine", NOT "saved-engine"
        assert result_state["engine"].name == "cli-engine"
        assert result_state["other_data"] == "value"


@pytest.mark.asyncio
async def test_engine_priority_saved_used_if_no_cli():
    """Verify that saved state engine is used if no CLI argument provided."""

    # Setup mocks
    mock_graph = AsyncMock()
    mock_graph.ainvoke.side_effect = lambda x: x

    with (
        patch(
            "copium_loop.copium_loop.get_engine",
            side_effect=lambda _: MockEngine("default-engine"),
        ),
        patch("copium_loop.copium_loop.create_graph", return_value=mock_graph),
        patch(
            "copium_loop.copium_loop.is_git_repo", new_callable=AsyncMock
        ) as mock_is_git,
        patch(
            "copium_loop.copium_loop.run_command", new_callable=AsyncMock
        ) as mock_run,
        patch("copium_loop.copium_loop.get_test_command", return_value=("echo", [])),
        patch("copium_loop.copium_loop.get_telemetry", return_value=MagicMock()),
    ):
        mock_is_git.return_value = False
        mock_run.return_value = {"exit_code": 0}

        # Case 2: No CLI engine provided (None)
        mgr = WorkflowManager(engine_name=None)
        mgr.graph = mock_graph
        mgr.verify_environment = AsyncMock(return_value=True)

        saved_engine = MockEngine("saved-engine")
        initial_state = {"engine": saved_engine, "other_data": "value"}

        result_state = await mgr.run("test prompt", initial_state=initial_state)

        # Expectation: The engine used should be "saved-engine"
        assert result_state["engine"].name == "saved-engine"
        assert result_state["other_data"] == "value"
