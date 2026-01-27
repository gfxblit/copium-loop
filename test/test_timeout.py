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
