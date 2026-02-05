import asyncio
import contextlib
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop import shell


@pytest.mark.asyncio
async def test_run_command_strips_null_bytes():
    """Test that run_command strips null bytes."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b"file1\x00.txt\n", b""])
        mock_proc.stderr.read = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        result = await shell.run_command("ls")

        assert "\x00" not in result["output"]
        assert result["output"] == "file1.txt\n"


@pytest.mark.asyncio
async def test_run_command_strips_ansi():
    """Test that run_command strips ANSI codes."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.stdout.read = AsyncMock(side_effect=[b"\x1b[31mRed Text\x1b[0m", b""])
        mock_proc.stderr.read = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        result = await shell.run_command("ls")

        assert result["output"] == "Red Text"


@pytest.mark.asyncio
async def test_run_command_timeout():
    """Test that run_command handles timeout."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()

        # Mock for stdout stream that hangs on second read
        class MockStream:
            def __init__(self):
                self.calls = 0

            async def read(self, _n):
                self.calls += 1
                if self.calls == 1:
                    return b"working..."

        mock_proc.stdout = MockStream()
        mock_proc.stderr.read = AsyncMock(return_value=b"")

        async def mock_wait():
            # Simulate waiting for the process to be killed or exit
            await asyncio.sleep(0.5)  # Give some time for kill to be called
            return -1  # Indicate a killed process

        mock_proc.wait = AsyncMock(side_effect=mock_wait)
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_exec.return_value = mock_proc

        # Set a very short timeout
        result = await shell.run_command("sleep", ["10"], command_timeout=0.1)
        assert "TIMEOUT" in result["output"]
        assert result["exit_code"] == -1
        assert mock_proc.kill.called


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

        task = asyncio.create_task(shell.run_command(cmd[0], cmd[1:]))

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

    res = await shell.run_command(cmd[0], cmd[1:])
    output_len = len(res["output"])

    # This assertion is expected to pass because we have MAX_OUTPUT_SIZE in shell.py
    assert output_len <= LIMIT + 2048, (
        f"Output length {output_len} exceeds limit {LIMIT}"
    )


@pytest.mark.asyncio
async def test_run_command_total_timeout_exceeded():
    """
    Test that run_command kills a process if total_timeout is exceeded.
    """
    import time

    # Use a sleep duration longer than the total_timeout
    sleep_duration = 2
    total_timeout = 0.5  # Shorter than sleep_duration
    start_time = time.monotonic()
    result = await shell.run_command(
        "sleep", [str(sleep_duration)], node="test", command_timeout=total_timeout
    )
    end_time = time.monotonic()

    # Assert that the command was terminated due to timeout
    assert result["exit_code"] == -1
    assert "TIMEOUT" in result["output"]
    assert (end_time - start_time) < sleep_duration
    # Allow for some delay in detection, but ensure it's close to total_timeout
    assert (end_time - start_time) >= total_timeout - 0.2


@pytest.mark.asyncio
async def test_run_command_total_timeout_not_exceeded():
    """
    Test that run_command completes successfully if total_timeout is not exceeded.
    """
    sleep_duration = 0.1
    total_timeout = 2  # Longer than sleep_duration

    result = await shell.run_command(
        "sleep", [str(sleep_duration)], node="test", command_timeout=total_timeout
    )

    # Assert that the command completed successfully
    assert result["exit_code"] == 0
    assert "[TIMEOUT]" not in result["output"]


@pytest.mark.asyncio
async def test_run_command_inactivity_timeout():
    """Test that run_command kills the process after inactivity timeout."""
    # We'll mock the timeout to be very short for the test
    with (
        patch("copium_loop.shell.INACTIVITY_TIMEOUT", 0.01),
        patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_proc = AsyncMock()
        killed_event = asyncio.Event()

        async def slow_read(*_args, **_kwargs):
            with contextlib.suppress(asyncio.TimeoutError):
                # Wait until killed or 1.0s passes
                await asyncio.wait_for(killed_event.wait(), timeout=1.0)
            return b""

        mock_proc.stdout.read = AsyncMock(side_effect=slow_read)
        mock_proc.stderr.read = AsyncMock(side_effect=slow_read)

        async def mock_wait():
            await killed_event.wait()
            return -1

        mock_proc.wait = AsyncMock(side_effect=mock_wait)
        mock_proc.returncode = None
        mock_proc.kill = MagicMock(side_effect=killed_event.set)
        mock_proc.terminate = MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        result = await shell.run_command(
            "slow_command"
        )  # Check if kill or terminate was called
        assert mock_proc.kill.called or mock_proc.terminate.called
        assert "[TIMEOUT]" in result["output"]


@pytest.mark.asyncio
async def test_run_command_total_timeout_while_streaming():
    """Test that run_command kills the process after total timeout even if streaming."""
    # Mock INACTIVITY_TIMEOUT to be large, and total_timeout to be small
    total_timeout = 0.5
    with (
        patch("copium_loop.shell.INACTIVITY_TIMEOUT", 10.0),
        patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_proc = AsyncMock()
        killed_event = asyncio.Event()

        # Simulate continuous streaming
        async def streaming_read(*_args, **_kwargs):
            while not killed_event.is_set():
                await asyncio.sleep(0.1)
                return b"streaming data\n"
            return b""

        mock_proc.stdout.read = AsyncMock(side_effect=streaming_read)
        mock_proc.stderr.read = AsyncMock(return_value=b"")

        async def mock_wait():
            await killed_event.wait()
            return -1

        mock_proc.wait = AsyncMock(side_effect=mock_wait)
        mock_proc.returncode = None
        mock_proc.kill = MagicMock(side_effect=killed_event.set)
        mock_proc.terminate = MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        start_time = asyncio.get_event_loop().time()
        result = await shell.run_command(
            "streaming_command", command_timeout=total_timeout
        )
        end_time = asyncio.get_event_loop().time()

        # Check if kill was called due to total timeout
        assert mock_proc.kill.called or mock_proc.terminate.called
        assert "[TIMEOUT]" in result["output"]
        assert "Process exceeded command_timeout" in result["output"]
        assert (end_time - start_time) < 2.0  # Should be relatively quick
        assert (end_time - start_time) >= total_timeout - 0.1


@pytest.mark.asyncio
async def test_run_command_default_inactivity_timeout():
    """Test that run_command uses the default INACTIVITY_TIMEOUT from constants."""
    with (
        patch("copium_loop.shell.INACTIVITY_TIMEOUT", 0.2),
        patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_proc = AsyncMock()
        killed_event = asyncio.Event()

        async def slow_read(*_args, **_kwargs):
            await killed_event.wait()
            return b""

        mock_proc.stdout.read = AsyncMock(side_effect=slow_read)
        mock_proc.stderr.read = AsyncMock(return_value=b"")

        async def mock_wait():
            await killed_event.wait()
            return -1

        mock_proc.wait = AsyncMock(side_effect=mock_wait)
        mock_proc.returncode = None
        mock_proc.kill = MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        start_time = asyncio.get_event_loop().time()
        # No timeouts passed, should use defaults
        result = await shell.run_command("default_timeout_command")
        end_time = asyncio.get_event_loop().time()

        assert mock_proc.kill.called
        assert "No output for 0.2s" in result["output"]
        assert (end_time - start_time) >= 0.2
        assert (end_time - start_time) < 0.5


@pytest.mark.asyncio
async def test_run_command_default_total_timeout_streaming():
    """Test that run_command uses the default COMMAND_TIMEOUT even when streaming."""
    with (
        patch("copium_loop.shell.INACTIVITY_TIMEOUT", 10.0),
        patch("copium_loop.shell.COMMAND_TIMEOUT", 0.3),
        patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_proc = AsyncMock()
        killed_event = asyncio.Event()

        async def streaming_read(*_args, **_kwargs):
            while not killed_event.is_set():
                await asyncio.sleep(0.05)
                return b"streaming...\n"
            return b""

        mock_proc.stdout.read = AsyncMock(side_effect=streaming_read)
        mock_proc.stderr.read = AsyncMock(return_value=b"")

        async def mock_wait():
            await killed_event.wait()
            return -1

        mock_proc.wait = AsyncMock(side_effect=mock_wait)
        mock_proc.returncode = None
        mock_proc.kill = MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        start_time = asyncio.get_event_loop().time()
        result = await shell.run_command("default_total_timeout_command")
        end_time = asyncio.get_event_loop().time()

        assert mock_proc.kill.called
        assert "exceeded command_timeout of 0.3s" in result["output"]
        assert (end_time - start_time) >= 0.3
        assert (end_time - start_time) < 0.6
