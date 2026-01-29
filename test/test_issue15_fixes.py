import asyncio
import contextlib
import os
import sys

import pytest

from copium_loop.utils import run_command


@pytest.mark.asyncio
async def test_orphaned_subprocess_on_cancellation():
    """
    Test that a subprocess is killed when the parent task is cancelled.
    This simulates the scenario where a node times out and cancels its children.
    """
    # Create a dummy script that runs for a long time and ignores SIGTERM if possible (to test force kill)
    # or just sleeps. simple sleep is enough to test if we attempt to kill it.

    # We use a python script as the child process to easily check if it's running
    child_script = """
import time
import sys
import os
print(f"Child PID: {os.getpid()}", flush=True)
try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    pass
"""

    # Run the command wrapped in a task
    cmd = [sys.executable, "-c", child_script]

    task = asyncio.create_task(run_command(cmd[0], cmd[1:]))

    # Wait a bit for the process to start (run_command starts the subprocess)
    # run_command will stream output. We can't easily get the PID from run_command directly
    # without modifying it to return it or parsing the output if we added logging.
    # But checking if a process exists requires the PID.

    # Modification: run_command returns a dict with 'output'. It waits for the process to finish.
    # So we can't get the PID from it easily *while* it's running unless we spy on `asyncio.create_subprocess_exec`
    # or change run_command to return the process object (which it doesn't).

    # Strategy: verification by side effect?
    # or we can mock `asyncio.create_subprocess_exec` to capture the process object.

    process_spy = {}
    original_create_subprocess_exec = asyncio.create_subprocess_exec

    async def mock_subprocess_exec(*args, **kwargs):
        process = await original_create_subprocess_exec(*args, **kwargs)
        process_spy["process"] = process
        return process

    with pytest.MonkeyPatch.context() as m:
        m.setattr(asyncio, "create_subprocess_exec", mock_subprocess_exec)

        task = asyncio.create_task(run_command(cmd[0], cmd[1:]))

        # Give it time to start
        await asyncio.sleep(0.5)

        assert "process" in process_spy, "Subprocess should have started"
        proc = process_spy["process"]
        pid = proc.pid

        # Check if process is running (signal 0)
        try:
            os.kill(pid, 0)
        except OSError:
            pytest.fail("Subprocess should be running")

        # Now cancel the task (simulating a timeout in _wrap_node)
        task.cancel()

        with contextlib.suppress(asyncio.CancelledError):
            await task

        # Give it a moment to cleanup
        await asyncio.sleep(0.5)

        # Check if process is still running
        is_running = True
        try:
            os.kill(pid, 0)
        except OSError:
            is_running = False

        assert not is_running, (
            f"Subprocess {pid} should have been killed after task cancellation"
        )


@pytest.mark.asyncio
async def test_unbounded_output_limit():
    """
    Test that the captured output is truncated if it exceeds a limit.
    """
    # Generate a lot of output
    long_output_script = """
print("A" * 1024 * 1024 * 10) # 10MB
"""
    cmd = [sys.executable, "-c", long_output_script]

    # We need to configure a limit. Since we haven't implemented it yet,
    # we expect this to return the full 10MB (or fail/crash if we were testing for crash).
    # To TDD this, we'll assert that the output length is capped at a default (e.g. 1MB or similar)
    # But currently it is NOT capped. So this test will fail if we assert < 10MB.

    # Let's assume we want to cap it at 1MB (1024*1024).
    LIMIT = 1024 * 1024

    # We might need to inject this limit or set it via env var or constant.
    # For now let's assume a constant we will add.

    res = await run_command(cmd[0], cmd[1:])
    output_len = len(res["output"])

    # This assertion is expected to fail currently
    assert output_len <= LIMIT + 1024, (
        f"Output length {output_len} exceeds limit {LIMIT}"
    )
