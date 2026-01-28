import asyncio
import contextlib
import unittest.mock
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import utils


@pytest.mark.asyncio
async def test_run_command_inactivity_timeout():
    """Test that run_command kills the process after inactivity timeout."""
    # We'll mock the timeout to be very short for the test
    with (
        patch("copium_loop.utils.INACTIVITY_TIMEOUT", 0.01),
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
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = None
        mock_proc.kill = unittest.mock.MagicMock(side_effect=killed_event.set)
        mock_proc.terminate = unittest.mock.MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        result = await utils.run_command("slow_command")

        # Check if kill or terminate was called
        assert mock_proc.kill.called or mock_proc.terminate.called
        assert "[TIMEOUT]" in result["output"]


@pytest.mark.asyncio
async def test_execute_gemini_inactivity_timeout():
    """Test that _execute_gemini kills the process after inactivity timeout."""
    with (
        patch("copium_loop.utils.INACTIVITY_TIMEOUT", 0.01),
        patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_proc = AsyncMock()
        killed_event = asyncio.Event()

        async def slow_read(*_args, **_kwargs):
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(killed_event.wait(), timeout=1.0)
            return b""

        mock_proc.stdout.read = AsyncMock(side_effect=slow_read)
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = None
        mock_proc.kill = unittest.mock.MagicMock(side_effect=killed_event.set)
        mock_proc.terminate = unittest.mock.MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        with pytest.raises(Exception) as excinfo:
            await utils._execute_gemini("prompt", "model")

        assert "TIMEOUT" in str(excinfo.value)
        assert mock_proc.kill.called or mock_proc.terminate.called


@pytest.mark.asyncio
async def test_run_command_total_timeout_while_streaming():
    """Test that run_command kills the process after total timeout even if streaming."""
    # Mock INACTIVITY_TIMEOUT to be large, and total_timeout to be small
    total_timeout = 0.5
    with (
        patch("copium_loop.utils.INACTIVITY_TIMEOUT", 10.0),
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
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = None
        mock_proc.kill = unittest.mock.MagicMock(side_effect=killed_event.set)
        mock_proc.terminate = unittest.mock.MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        start_time = asyncio.get_event_loop().time()
        result = await utils.run_command("streaming_command", total_timeout=total_timeout)
        end_time = asyncio.get_event_loop().time()

        # Check if kill was called due to total timeout
        assert mock_proc.kill.called or mock_proc.terminate.called
        assert "[TIMEOUT]" in result["output"]
        assert "Process exceeded total_timeout" in result["output"]
        assert (end_time - start_time) < 2.0  # Should be relatively quick
        assert (end_time - start_time) >= total_timeout - 0.1


@pytest.mark.asyncio
async def test_run_command_default_inactivity_timeout():
    """Test that run_command uses the default INACTIVITY_TIMEOUT from constants."""
    # We patch the constant in constants.py and see if utils uses it
    with (
        patch("copium_loop.utils.INACTIVITY_TIMEOUT", 0.2),
        patch("asyncio.create_subprocess_exec") as mock_exec,
    ):
        mock_proc = AsyncMock()
        killed_event = asyncio.Event()

        async def slow_read(*_args, **_kwargs):
            await killed_event.wait()
            return b""

        mock_proc.stdout.read = AsyncMock(side_effect=slow_read)
        mock_proc.stderr.read = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = None
        mock_proc.kill = unittest.mock.MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        start_time = asyncio.get_event_loop().time()
        # No timeouts passed, should use defaults
        result = await utils.run_command("default_timeout_command")
        end_time = asyncio.get_event_loop().time()

        assert mock_proc.kill.called
        assert "No output for 0.2s" in result["output"]
        assert (end_time - start_time) >= 0.2
        assert (end_time - start_time) < 0.5


@pytest.mark.asyncio
async def test_run_command_default_total_timeout_streaming():
    """Test that run_command uses the default TOTAL_TIMEOUT even when streaming."""
    with (
        patch("copium_loop.utils.INACTIVITY_TIMEOUT", 10.0),
        patch("copium_loop.utils.TOTAL_TIMEOUT", 0.3),
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
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = None
        mock_proc.kill = unittest.mock.MagicMock(side_effect=killed_event.set)
        mock_exec.return_value = mock_proc

        start_time = asyncio.get_event_loop().time()
        result = await utils.run_command("default_total_timeout_command")
        end_time = asyncio.get_event_loop().time()

        assert mock_proc.kill.called
        assert "exceeded total_timeout of 0.3s" in result["output"]
        assert (end_time - start_time) >= 0.3
        assert (end_time - start_time) < 0.6
