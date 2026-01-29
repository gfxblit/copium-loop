import os
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import notifications


class TestNotifications:
    """Tests for notification system."""

    @pytest.mark.asyncio
    async def test_notify_does_nothing_without_channel(self):
        """Test that notify does nothing when NTFY_CHANNEL is not set."""
        if "NTFY_CHANNEL" in os.environ:
            del os.environ["NTFY_CHANNEL"]

        with patch("copium_loop.notifications.run_command", new_callable=AsyncMock) as mock_run:
            await notifications.notify("Title", "Message")
            mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_calls_curl_with_channel(self):
        """Test that notify calls curl when NTFY_CHANNEL is set."""
        os.environ["NTFY_CHANNEL"] = "test-channel"

        with (
            patch("copium_loop.notifications.get_tmux_session", return_value="test-session"),
            patch("copium_loop.notifications.run_command", new_callable=AsyncMock) as mock_run,
        ):
            await notifications.notify("Title", "Message", 4)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][1]
            assert "Title: Title" in args
            assert "Priority: 4" in args
            assert "test-channel" in args[-1]

@pytest.mark.asyncio
async def test_get_tmux_session():
    """Test getting tmux session name."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"my-session\n", b""))
        mock_exec.return_value = mock_proc

        session = await notifications.get_tmux_session()
        assert session == "my-session"

@pytest.mark.asyncio
async def test_get_tmux_session_no_tmux():
    """Test fallback when tmux is not available."""
    with patch("asyncio.create_subprocess_exec") as mock_exec:
        mock_exec.side_effect = Exception("tmux not found")

        session = await notifications.get_tmux_session()
        assert session == "no-tmux"
