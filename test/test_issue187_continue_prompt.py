import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import contextlib
from copium_loop.__main__ import async_main

@pytest.mark.asyncio
async def test_continue_ignores_new_prompt_currently():
    """
    Verify that currently, providing a prompt with --continue ignores the new prompt
    and uses the old one from state.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        # Simulate 'copium-loop -c "new prompt"'
        mock_args = MagicMock()
        mock_args.continue_session = True
        mock_args.prompt = ["new", "prompt"]
        mock_args.node = "coder"
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            # Mock get_last_incomplete_node to return a node so we can continue
            mock_telemetry.get_last_incomplete_node.return_value = ("coder", {})
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                # Mock existing state with OLD prompt
                mock_sm.get_agent_state.return_value = {"prompt": "OLD PROMPT"}
                mock_sm.get_metadata.return_value = "current-branch"
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm_cls.return_value = mock_sm

                with patch("copium_loop.copium_loop.WorkflowManager") as mock_wm_cls:
                    mock_wm = MagicMock()
                    mock_wm.run = MagicMock()
                    mock_wm.notify = AsyncMock()  # Make notify awaitable
                    # We need run to match signature and be awaitable
                    async def mock_run(_prompt, _initial_state=None):
                        return {"review_status": "approved", "test_output": "PASS"}
                    mock_wm.run.side_effect = mock_run
                    mock_wm_cls.return_value = mock_wm

                    with patch("copium_loop.git.get_current_branch", new_callable=AsyncMock) as mock_branch:
                        mock_branch.return_value = "current-branch"

                        # Run main
                        with contextlib.suppress(SystemExit):
                            await async_main()

                        # Verify what prompt was passed to WorkflowManager.run
                        # Currently we expect "new prompt" because the code now respects the override
                        args, _ = mock_wm.run.call_args
                        passed_prompt = args[0]
                        assert passed_prompt == "new prompt"
