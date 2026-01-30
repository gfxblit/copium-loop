import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.shell import (
    ProcessMonitor,
    StreamLogger,
    _clean_chunk,
    stream_subprocess,
)


@pytest.mark.asyncio
async def test_stream_logger_no_chunk():
    """Test StreamLogger.process_chunk with empty chunk."""
    logger = StreamLogger(node="test")
    with patch("sys.stdout.write") as mock_write:
        logger.process_chunk("")
        mock_write.assert_not_called()


@pytest.mark.asyncio
async def test_stream_logger_with_telemetry():
    """Test StreamLogger buffering and telemetry logging."""
    with patch("copium_loop.shell.get_telemetry") as mock_get_telemetry:
        mock_telemetry = MagicMock()
        mock_get_telemetry.return_value = mock_telemetry

        logger = StreamLogger(node="test")
        logger.process_chunk("line1\nline2")

        mock_telemetry.log_output.assert_called_once_with("test", "line1\n")
        assert logger.buffer == "line2"

        logger.flush()
        mock_telemetry.log_output.assert_called_with("test", "line2")
        assert logger.buffer == ""


@pytest.mark.asyncio
async def test_process_monitor_early_exit():
    """Test ProcessMonitor exits early if process finishes."""
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    monitor = ProcessMonitor(mock_proc, 0, 10, 10, "test")

    # This should return almost immediately
    await asyncio.wait_for(monitor.run(), timeout=1.0)


@pytest.mark.asyncio
async def test_process_monitor_sync_callback_and_exception():
    """Test ProcessMonitor with synchronous callback and exception handling."""
    import time

    mock_proc = MagicMock()
    mock_proc.returncode = None
    # kill() succeeds now

    sync_callback_called = False

    def sync_callback(_msg):
        nonlocal sync_callback_called
        sync_callback_called = True

    monitor = ProcessMonitor(
        mock_proc,
        start_time=time.monotonic() - 20,
        command_timeout=10,
        inactivity_timeout=10,
        node="test",
        on_timeout_callback=sync_callback,
    )

    with patch("copium_loop.shell.get_telemetry", return_value=None):
        await monitor.run()
        assert sync_callback_called


@pytest.mark.asyncio
async def test_process_monitor_kill_exception():
    """Test ProcessMonitor exception handling when kill fails."""
    import time

    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.kill.side_effect = Exception("kill failed")

    monitor = ProcessMonitor(
        mock_proc,
        start_time=time.monotonic() - 20,
        command_timeout=10,
        inactivity_timeout=10,
        node="test",
    )

    with patch("copium_loop.shell.get_telemetry", return_value=None):
        await monitor.run()
        # Should finish without raising exception


def test_clean_chunk_non_string():
    """Test _clean_chunk with non-string/bytes input."""
    assert _clean_chunk(123) == "123"


def test_clean_chunk_decode_error():
    """Test _clean_chunk with decode error."""
    mock_bytes = MagicMock(spec=bytes)
    mock_bytes.decode.side_effect = Exception("decode error")

    with patch(
        "copium_loop.shell.isinstance",
        side_effect=lambda x, t: True if t is bytes else isinstance(x, t),
    ):
        assert _clean_chunk(mock_bytes) == ""


@pytest.mark.asyncio
async def test_stream_subprocess_process_lookup_error():
    """Test stream_subprocess handles ProcessLookupError during cleanup."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = MagicMock()
        mock_proc.stdout.read = AsyncMock(return_value=b"")
        mock_proc.stderr.read = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = None
        mock_proc.kill = MagicMock(side_effect=ProcessLookupError())
        mock_exec.return_value = mock_proc

        await stream_subprocess("ls", [], {}, "test", 10)
