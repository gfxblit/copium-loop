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
async def test_completed_session_no_node_exits():
    """
    Case A: Session completed, no -n flag -> Exit 0 (Current behavior preserved).
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = True
        mock_args.prompt = []
        mock_args.node = None  # Default value
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            # Simulate completed workflow
            mock_telemetry.get_last_incomplete_node.return_value = (
                None,
                {"reason": "workflow_completed", "status": "success"},
            )
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm.get_repo_root.return_value = "/test/repo"
                mock_sm.get_agent_state.return_value = {"prompt": "foo"}
                mock_sm_cls.return_value = mock_sm

                with patch(
                    "copium_loop.git.get_current_branch", new_callable=AsyncMock
                ) as mock_branch:
                    mock_branch.return_value = "current-branch"

                    # Expect SystemExit(0)
                    with pytest.raises(SystemExit) as excinfo:
                        await async_main()
                    assert excinfo.value.code == 0


@pytest.mark.asyncio
async def test_completed_session_with_node_continues():
    """
    Case B: Session completed, -n pr_pre_checker flag -> Workflow starts at pr_pre_checker.
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = True
        mock_args.prompt = []
        mock_args.node = "pr_pre_checker"  # Explicitly provided
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            # Simulate completed workflow
            mock_telemetry.get_last_incomplete_node.return_value = (
                None,
                {"reason": "workflow_completed", "status": "success"},
            )
            mock_telemetry.reconstruct_state.return_value = {
                "prompt": "persisted prompt"
            }
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm.get_repo_root.return_value = "/test/repo"
                mock_sm.get_agent_state.return_value = {"prompt": "persisted prompt"}
                mock_sm.get_original_prompt.return_value = "persisted prompt"
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

                        # Verify that WorkflowManager was initialized with start_node="pr_pre_checker"
                        args, kwargs = mock_wm_cls.call_args
                        assert kwargs["start_node"] == "pr_pre_checker"


@pytest.mark.asyncio
async def test_incomplete_session_with_node_overrides_resume_node():
    """
    Case C: Session incomplete, -n flag -> Workflow starts at requested node (Existing behavior preserved).
    """
    with patch("argparse.ArgumentParser.parse_args") as mock_parse:
        mock_args = MagicMock()
        mock_args.continue_session = True
        mock_args.prompt = []
        mock_args.node = "reviewer"  # Explicitly provided
        mock_args.verbose = False
        mock_args.monitor = False
        mock_args.engine = None
        mock_parse.return_value = mock_args

        with patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_telemetry.session_id = "test-session"
            # Simulate incomplete workflow that would normally resume at 'tester'
            mock_telemetry.get_last_incomplete_node.return_value = ("tester", {})
            mock_telemetry.reconstruct_state.return_value = {
                "prompt": "persisted prompt"
            }
            mock_get_telemetry.return_value = mock_telemetry

            with patch("copium_loop.session_manager.SessionManager") as mock_sm_cls:
                mock_sm = MagicMock()
                mock_sm.get_branch_name.return_value = "current-branch"
                mock_sm.get_repo_root.return_value = "/test/repo"
                mock_sm.get_agent_state.return_value = {"prompt": "persisted prompt"}
                mock_sm.get_original_prompt.return_value = "persisted prompt"
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

                        # Verify that WorkflowManager was initialized with start_node="reviewer" (overriding "tester")
                        args, kwargs = mock_wm_cls.call_args
                        assert kwargs["start_node"] == "reviewer"
