import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.__main__ import async_main


@pytest.fixture(autouse=True)
def mock_repo_root():
    with patch("copium_loop.shell.run_command") as mock_run:
        # Default mock for git rev-parse --show-toplevel
        mock_run.return_value = {"exit_code": 0, "output": "/test/repo"}
        yield mock_run


@pytest.mark.asyncio
async def test_retry_count_reset_on_explicit_continue():
    """
    Verify that retry_count is reset to 0 when --continue is used.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = True
        mock_args.prompt = []
        mock_args.node = None
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            mock_telemetry.get_last_incomplete_node.return_value = ("tester", {})
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm.get_repo_root.return_value = "/test/repo"
                # Mock state with max retries
                mock_sm.get_agent_state.return_value = {
                    "prompt": "foo",
                    "retry_count": 10,
                }
                mock_sm.get_original_prompt.return_value = "foo"
                mock_sm_cls.return_value = mock_sm

                with patch("copium_loop.copium_loop.WorkflowManager") as mock_wm_cls:
                    mock_wm = MagicMock()
                    mock_wm.run = AsyncMock(
                        return_value={
                            "review_status": "approved",
                            "test_output": "PASS",
                        }
                    )
                    mock_wm.notify = AsyncMock()
                    mock_wm_cls.return_value = mock_wm

                    with patch(
                        "copium_loop.git.get_current_branch", new_callable=AsyncMock
                    ) as mock_branch:
                        mock_branch.return_value = "current-branch"

                        with contextlib.suppress(SystemExit):
                            await async_main()

                        args, kwargs = mock_wm.run.call_args
                        initial_state = kwargs["initial_state"]
                        assert initial_state["retry_count"] == 0


@pytest.mark.asyncio
async def test_retry_count_reset_on_explicit_node():
    """
    Verify that retry_count is reset to 0 when --node is used (which triggers resume).
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = False
        mock_args.prompt = []
        mock_args.node = "tester"
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            mock_telemetry.get_last_incomplete_node.return_value = ("tester", {})
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm.get_repo_root.return_value = "/test/repo"
                # Implicit resume happens because session exists and no prompt provided
                mock_sm.get_agent_state.return_value = {
                    "prompt": "foo",
                    "retry_count": 10,
                }
                mock_sm.get_original_prompt.return_value = "foo"
                mock_sm_cls.return_value = mock_sm

                with patch("copium_loop.copium_loop.WorkflowManager") as mock_wm_cls:
                    mock_wm = MagicMock()
                    mock_wm.run = AsyncMock(
                        return_value={
                            "review_status": "approved",
                            "test_output": "PASS",
                        }
                    )
                    mock_wm.notify = AsyncMock()
                    mock_wm_cls.return_value = mock_wm

                    with patch(
                        "copium_loop.git.get_current_branch", new_callable=AsyncMock
                    ) as mock_branch:
                        mock_branch.return_value = "current-branch"

                        with contextlib.suppress(SystemExit):
                            await async_main()

                        args, kwargs = mock_wm.run.call_args
                        initial_state = kwargs["initial_state"]
                        assert initial_state["retry_count"] == 0


@pytest.mark.asyncio
async def test_retry_count_reset_on_implicit_resume():
    """
    Verify that retry_count is reset to 0 when session is implicitly resumed.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = False
        mock_args.prompt = []  # No prompt triggers implicit resume if session exists
        mock_args.node = None
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            mock_telemetry.get_last_incomplete_node.return_value = ("tester", {})
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm.get_repo_root.return_value = "/test/repo"
                mock_sm.get_agent_state.return_value = {
                    "prompt": "foo",
                    "retry_count": 10,
                }
                mock_sm.get_original_prompt.return_value = "foo"
                mock_sm_cls.return_value = mock_sm

                with patch("copium_loop.copium_loop.WorkflowManager") as mock_wm_cls:
                    mock_wm = MagicMock()
                    mock_wm.run = AsyncMock(
                        return_value={
                            "review_status": "approved",
                            "test_output": "PASS",
                        }
                    )
                    mock_wm.notify = AsyncMock()
                    mock_wm_cls.return_value = mock_wm

                    with patch(
                        "copium_loop.git.get_current_branch", new_callable=AsyncMock
                    ) as mock_branch:
                        mock_branch.return_value = "current-branch"

                        with contextlib.suppress(SystemExit):
                            await async_main()

                        args, kwargs = mock_wm.run.call_args
                        initial_state = kwargs["initial_state"]
                        assert initial_state["retry_count"] == 0
