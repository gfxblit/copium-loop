import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.__main__ import async_main


@pytest.fixture(autouse=True)
def mock_repo_root():
    with patch("copium_loop.shell.run_command") as mock_run:
        mock_run.return_value = {"exit_code": 0, "output": "/test/repo"}
        yield mock_run


@pytest.mark.asyncio
async def test_fresh_start_with_prompt():
    """
    Test that if a prompt is provided, it starts fresh even if a session exists.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = False
        mock_args.prompt = ["new", "prompt"]
        mock_args.node = None
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                # Existing session exists
                mock_sm.get_agent_state.return_value = {"prompt": "old prompt"}
                mock_sm.get_original_prompt.return_value = "old prompt"
                mock_sm_cls.return_value = mock_sm

                with patch("copium_loop.copium_loop.WorkflowManager") as mock_wm_cls:
                    mock_wm = MagicMock()
                    mock_wm.run = MagicMock()
                    mock_wm.notify = AsyncMock()

                    async def mock_run(_prompt, _initial_state=None):
                        return {"review_status": "approved", "test_output": "PASS"}

                    mock_wm.run.side_effect = mock_run
                    mock_wm_cls.return_value = mock_wm

                    with patch(
                        "copium_loop.git.get_current_branch", new_callable=AsyncMock
                    ) as mock_branch:
                        mock_branch.return_value = "current-branch"

                        with contextlib.suppress(SystemExit):
                            await async_main()

                        # Verify that WorkflowManager was initialized with start_node="coder" (default)
                        # and NOT the resume node.
                        args, kwargs = mock_wm_cls.call_args
                        assert kwargs["start_node"] == "coder"

                        # Verify run was called with NEW prompt
                        args_run, _ = mock_wm.run.call_args
                        assert args_run[0] == "new prompt"

                        # Verify initial_state had the new prompt
                        _, kwargs_run = mock_wm.run.call_args
                        assert kwargs_run["initial_state"]["prompt"] == "new prompt"


@pytest.mark.asyncio
async def test_continue_with_prompt_override():
    """
    Test that --continue with a prompt overrides the stored prompt but resumes from last node.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = True
        mock_args.prompt = ["overridden", "prompt"]
        mock_args.node = None
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            mock_telemetry.get_last_incomplete_node.return_value = ("tester", {})
            mock_telemetry.reconstruct_state.return_value = {"foo": "bar"}
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm.get_agent_state.return_value = {"foo": "bar"}
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm.get_repo_root.return_value = "/test/repo"
                mock_sm.get_original_prompt.return_value = "old prompt"
                mock_sm_cls.return_value = mock_sm

                with patch("copium_loop.copium_loop.WorkflowManager") as mock_wm_cls:
                    mock_wm = MagicMock()
                    mock_wm.run = MagicMock()
                    mock_wm.notify = AsyncMock()

                    async def mock_run(_prompt, _initial_state=None):
                        return {"review_status": "approved", "test_output": "PASS"}

                    mock_wm.run.side_effect = mock_run
                    mock_wm_cls.return_value = mock_wm

                    with patch(
                        "copium_loop.git.get_current_branch", new_callable=AsyncMock
                    ) as mock_branch:
                        mock_branch.return_value = "current-branch"

                        with contextlib.suppress(SystemExit):
                            await async_main()

                        # Verify that WorkflowManager was initialized with start_node="tester"
                        args, kwargs = mock_wm_cls.call_args
                        assert kwargs["start_node"] == "tester"

                        # Verify run was called with OVERRIDDEN prompt
                        args_run, _ = mock_wm.run.call_args
                        assert args_run[0] == "overridden prompt"
