import asyncio
import os
import sys
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(os.path.abspath("src"))

from copium_loop.constants import MAX_RETRIES
from copium_loop.session_manager import SessionManager


async def reproduce_issue():
    session_id = "test-session-retry"
    sm = SessionManager(session_id)

    # Simulate a session that hit max retries
    state = {
        "retry_count": MAX_RETRIES,
        "prompt": "Fix something",
        "engine_name": "gemini",
    }
    sm.update_agent_state(state)
    sm.update_session_info(
        branch_name="main",
        repo_root="/tmp",
        engine_name="gemini",
        original_prompt="Fix something",
    )

    print(f"Stored retry_count: {sm.get_agent_state().get('retry_count')}")

    # Now simulate running with --continue flag

    from copium_loop.__main__ import async_main

    test_args = ["copium-loop", "--continue"]

    # We mock NTFY_CHANNEL to avoid warnings
    os.environ["NTFY_CHANNEL"] = "test-channel"

    with (
        patch("sys.argv", test_args),
        patch("copium_loop.telemetry.get_telemetry") as mock_get_telemetry,
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch(
            "copium_loop.shell.run_command",
            return_value={"exit_code": 0, "output": "/tmp\n"},
        ),
        patch("copium_loop.copium_loop.WorkflowManager.run") as mock_run,
    ):
        mock_telemetry = MagicMock()
        mock_telemetry.session_id = session_id
        mock_get_telemetry.return_value = mock_telemetry

        # We need to mock telemetry.get_last_incomplete_node too
        mock_telemetry.get_last_incomplete_node.return_value = (
            "coder",
            {"reason": "incomplete"},
        )

        mock_run.return_value = {"review_status": "approved", "test_output": "PASS"}

        import contextlib

        with contextlib.suppress(SystemExit):
            await async_main()

        # Check what state was passed to workflow.run
        # It should be the second argument (initial_state)
        _, kwargs = mock_run.call_args
        initial_state = kwargs.get("initial_state")
        print(
            f"Initial state retry_count passed to workflow.run: {initial_state.get('retry_count')}"
        )

        if initial_state.get("retry_count") == MAX_RETRIES:
            print("ISSUE REPRODUCED: retry_count was NOT reset.")
        else:
            print("ISSUE NOT REPRODUCED: retry_count was reset.")


if __name__ == "__main__":
    asyncio.run(reproduce_issue())
