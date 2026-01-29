import asyncio
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
        mock_proc.stdout.read = AsyncMock(
            side_effect=[b"\x1b[31mRed Text\x1b[0m", b""]
        )
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
                await asyncio.sleep(2)
                return b""

        mock_proc.stdout = MockStream()
        mock_proc.stderr.read = AsyncMock(return_value=b"")
        mock_proc.wait = AsyncMock(return_value=0)
        mock_proc.returncode = None
        mock_proc.kill = MagicMock()
        mock_exec.return_value = mock_proc

        # Set a very short timeout
        result = await shell.run_command("sleep", ["10"], command_timeout=0.1)

        assert "TIMEOUT" in result["output"]
        assert result["exit_code"] == -1
        assert mock_proc.kill.called
