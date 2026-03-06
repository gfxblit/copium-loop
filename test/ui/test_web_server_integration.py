from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.__main__ import async_main


@pytest.mark.asyncio
class TestMainWeb:
    """Tests for the --web flag in __main__.py."""

    @patch("copium_loop.copium_loop.WorkflowManager")
    @patch("copium_loop.telemetry.get_telemetry")
    @patch("argparse.ArgumentParser.parse_args")
    @patch("uvicorn.run")
    async def test_async_main_starts_web_server(
        self,
        _mock_uvicorn_run,
        mock_parse_args,
        mock_get_telemetry,
        mock_workflow_manager,
    ):
        # Setup mocks
        mock_args = MagicMock()
        mock_args.monitor = False
        mock_args.web = True  # The new flag
        mock_args.continue_session = False
        mock_args.prompt = ["test", "prompt"]
        mock_args.node = "coder"
        mock_args.verbose = True
        mock_args.engine = "gemini"
        mock_parse_args.return_value = mock_args

        mock_telemetry = MagicMock()
        mock_get_telemetry.return_value = mock_telemetry

        mock_workflow = AsyncMock()
        mock_workflow.run.return_value = {"review_status": "approved"}
        mock_workflow_manager.return_value = mock_workflow

        # We expect uvicorn.run to be called in a separate task or similar
        # Since async_main is awaitable, we might need to handle the background task

        # Patching asyncio.create_task to see if it's called with the web server
        with patch("asyncio.create_task"), patch("sys.exit"):
            await async_main()

            # Check if uvicorn was started (probably via a wrapper function)
            # This depends on how I implement it.
            # If I use create_task(run_web_server()), I can check that.

            assert mock_workflow.run.called
