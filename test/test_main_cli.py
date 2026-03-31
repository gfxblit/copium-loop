import contextlib
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.__main__ import async_main


@pytest.mark.asyncio
async def test_cli_run_subcommand_compatibility():
    """Test that the default behavior still works as 'run'."""
    # Mock WorkflowManager and other dependencies to avoid actual execution
    with patch("copium_loop.copium_loop.WorkflowManager") as mock_workflow_manager:
        mock_instance = mock_workflow_manager.return_value
        mock_instance.run = AsyncMock(return_value={"review_status": "approved"})
        mock_instance.notify = AsyncMock()

        with patch("copium_loop.session_manager.SessionManager") as mock_session_manager:
            mock_session_manager.return_value.get_agent_state.return_value = None
            mock_session_manager.return_value.get_original_prompt.return_value = None

            with patch("sys.argv", ["copium-loop", "my prompt"]):
                with pytest.raises(SystemExit) as e:
                    await async_main()
                assert e.value.code == 0
                mock_workflow_manager.assert_called_once()
                # Verify it was called with "my prompt"
                args, _ = mock_instance.run.call_args
                assert args[0] == "my prompt"


@pytest.mark.asyncio
async def test_cli_workon_subcommand():
    """Test that the 'workon' subcommand is recognized."""
    # This should fail initially because workon is not implemented
    with (
        patch("copium_loop.workon.workon_main", new_callable=AsyncMock) as mock_workon_main,
        patch(
            "sys.argv",
            ["copium-loop", "workon", "https://github.com/owner/repo/issues/1"],
        ),
    ):
        with contextlib.suppress(SystemExit):
            await async_main()
        mock_workon_main.assert_called_once()
