import asyncio
import contextlib
import os
import sys

import pytest

from copium_loop.shell import run_command


@pytest.mark.asyncio
async def test_orphaned_subprocess_on_cancellation():
    """
    Test that a subprocess is killed when the parent task is cancelled.
    This simulates the scenario where a node times out and cancels its children.
    """
    # Use a python script as the child process to easily check if it's running
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

    LIMIT = 1024 * 1024

    res = await run_command(cmd[0], cmd[1:])
    output_len = len(res["output"])

    # This assertion is expected to pass because we have MAX_OUTPUT_SIZE in shell.py
    assert output_len <= LIMIT + 2048, (
        f"Output length {output_len} exceeds limit {LIMIT}"
    )
