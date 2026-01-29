import asyncio
import time
import unittest.mock

import pytest

from copium_loop.utils import invoke_gemini, run_command


@pytest.mark.asyncio
async def test_run_command_total_timeout_exceeded():
    """
    Test that run_command kills a process if total_timeout is exceeded.
    """
    # Use a sleep duration longer than the total_timeout
    sleep_duration = 5
    total_timeout = 2  # Shorter than sleep_duration
    start_time = time.monotonic()
    result = await run_command(
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
    sleep_duration = 1
    total_timeout = 10  # Longer than sleep_duration

    result = await run_command(
        "sleep", [str(sleep_duration)], node="test", command_timeout=total_timeout
    )

    # Assert that the command completed successfully
    assert result["exit_code"] == 0
    assert "[TIMEOUT]" not in result["output"]


@pytest.mark.asyncio
@unittest.mock.patch("asyncio.create_subprocess_exec")
async def test_invoke_gemini_total_timeout(mock_create_subprocess_exec):
    """
    Test that invoke_gemini kills the underlying Gemini CLI process if total_timeout is exceeded.
    """
    # Use an event to signal process completion or kill
    killed_event = asyncio.Event()

    # Mock the subprocess
    mock_process = unittest.mock.MagicMock()

    async def mock_read(_n=1024):
        await asyncio.sleep(0.01)
        return b""

    mock_process.stdout.read.side_effect = mock_read

    async def mock_wait():
        try:
            # Wait for either natural completion (not happening here) or kill
            await asyncio.wait_for(killed_event.wait(), timeout=10)
            return -1  # Return -1 if killed
        except asyncio.TimeoutError:
            return 0

    def mock_kill():
        killed_event.set()

    mock_process.wait.side_effect = mock_wait
    mock_process.kill.side_effect = mock_kill
    mock_process.returncode = None
    mock_create_subprocess_exec.return_value = mock_process

    # Set total_timeout shorter than the wait
    total_timeout = 1
    prompt = "test prompt"

    start_time = time.monotonic()
    with pytest.raises(Exception) as excinfo:
        await invoke_gemini(
            prompt, models=["test-model"], command_timeout=total_timeout, node="test"
        )
    end_time = time.monotonic()

    # Assertions
    assert "TIMEOUT" in str(excinfo.value)
    assert mock_process.kill.called
    assert (end_time - start_time) < 5
    assert (end_time - start_time) >= total_timeout - 0.2
