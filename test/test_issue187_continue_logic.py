import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.__main__ import async_main


@pytest.mark.asyncio
async def test_implicit_resumption():
    """
    Test that if no prompt is provided and a session exists, it implicitly resumes.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = False
        mock_args.prompt = []
        mock_args.node = "coder"
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            mock_telemetry.get_last_incomplete_node.return_value = ("tester", {})
            mock_telemetry.reconstruct_state.return_value = {}
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                # Simulate existing session state
                mock_sm.get_agent_state.return_value = {"prompt": "old prompt"}
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm.get_original_prompt.return_value = "old prompt"
                mock_sm.get_engine_name.return_value = "gemini"
                mock_sm_cls.return_value = mock_sm

                with patch("copium_loop.copium_loop.WorkflowManager") as mock_wm_cls:
                    mock_wm = MagicMock()
                    mock_wm.run = MagicMock()

                    async def mock_run(_prompt, _initial_state=None):
                        return {"review_status": "approved", "test_output": "PASS"}

                    mock_wm.run.side_effect = mock_run
                    mock_wm.notify = AsyncMock()
                    mock_wm_cls.return_value = mock_wm

                    with patch(
                        "copium_loop.git.get_current_branch", new_callable=AsyncMock
                    ) as mock_branch:
                        mock_branch.return_value = "current-branch"

                        with contextlib.suppress(SystemExit):
                            await async_main()

                        # Verify that we resumed
                        # WorkflowManager should be initialized with start_node="tester" (from telemetry)
                        args, kwargs = mock_wm_cls.call_args
                        assert kwargs["start_node"] == "tester"

                        # Verify run was called with old prompt
                        args_run, _ = mock_wm.run.call_args
                        assert args_run[0] == "old prompt"


@pytest.mark.asyncio
async def test_branch_mismatch_error():
    """
    Test that if the session branch differs from current branch, it exits with error.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = True
        mock_args.prompt = []
        mock_args.node = "coder"
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
                mock_sm.get_branch_name.return_value = "other-branch"
                mock_sm.get_agent_state.return_value = {"prompt": "foo"}
                mock_sm_cls.return_value = mock_sm

                with patch(
                    "copium_loop.git.get_current_branch", new_callable=AsyncMock
                ) as mock_branch:
                    mock_branch.return_value = "current-branch"

                    # Expect SystemExit(1)
                    with pytest.raises(SystemExit) as excinfo:
                        await async_main()
                    assert excinfo.value.code == 1


@pytest.mark.asyncio
async def test_explicit_continue_override():
    """
    Test that --continue with a prompt overrides the stored prompt.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
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
            mock_telemetry.get_last_incomplete_node.return_value = ("coder", {})
            mock_telemetry.reconstruct_state.return_value = {}
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm.get_agent_state.return_value = {"prompt": "old prompt"}
                mock_sm.get_branch_name.return_value = "current-branch"
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

                        # Verify run was called with NEW prompt
                        args_run, _ = mock_wm.run.call_args
                        assert args_run[0] == "new prompt"
