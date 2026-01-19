import os
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import utils


class TestHelpers:
    """Tests for helper functions."""

    @pytest.mark.asyncio
    async def test_run_command_strips_null_bytes(self):
        """Test that run_command strips null bytes."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(side_effect=[b"file1\x00.txt\n", b""])
            mock_proc.stderr.read = AsyncMock(return_value=b"")
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await utils.run_command("ls")

            assert "\x00" not in result["output"]
            assert result["output"] == "file1.txt\n"

    @pytest.mark.asyncio
    async def test_run_command_strips_ansi(self):
        """Test that run_command strips ANSI codes."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.stdout.read = AsyncMock(
                side_effect=[b"\x1b[31mRed Text\x1b[0m", b""]
            )
            mock_proc.stderr.read = AsyncMock(return_value=b"")
            mock_proc.wait = AsyncMock(return_value=0)
            mock_exec.return_value = mock_proc

            result = await utils.run_command("ls")

            assert result["output"] == "Red Text"

    @pytest.mark.asyncio
    async def test_get_tmux_session(self):
        """Test getting tmux session name."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"my-session\n", b""))
            mock_exec.return_value = mock_proc

            session = await utils.get_tmux_session()
            assert session == "my-session"

    @pytest.mark.asyncio
    async def test_get_tmux_session_no_tmux(self):
        """Test fallback when tmux is not available."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = Exception("tmux not found")

            session = await utils.get_tmux_session()
            assert session == "no-tmux"

    def test_get_test_command_pytest(self):
        """Test that get_test_command returns pytest for python projects."""

        def side_effect(path):
            return path == "pyproject.toml"

        with patch("os.path.exists", side_effect=side_effect):
            cmd, args = utils.get_test_command()
            assert cmd == "pytest"
            assert args == []

    def test_get_test_command_npm_priority(self):
        """Test that get_test_command returns npm if package.json exists, even if pyproject.toml exists."""

        def side_effect(path):
            return path in ["package.json", "pyproject.toml"]

        with patch("os.path.exists", side_effect=side_effect):
            cmd, args = utils.get_test_command()
            assert cmd == "npm"
            assert args == ["test"]

    def test_get_lint_command_ruff(self):
        """Test that get_lint_command returns ruff for python projects."""

        def side_effect(path):
            return path == "pyproject.toml"

        with patch("os.path.exists", side_effect=side_effect):
            cmd, args = utils.get_lint_command()
            assert cmd == "ruff"
            assert args == ["check", "."]

    def test_get_lint_command_npm_priority(self):
        """Test that get_lint_command returns npm if package.json exists, even if pyproject.toml exists."""

        def side_effect(path):
            return path in ["package.json", "pyproject.toml"]

        with patch("os.path.exists", side_effect=side_effect):
            cmd, args = utils.get_lint_command()
            assert cmd == "npm"
            assert args == ["run", "lint"]


class TestInvokeGemini:
    """Tests for Gemini CLI invocation with fallback."""

    @pytest.mark.asyncio
    async def test_invoke_gemini_success_first_model(self):
        """Test successful invocation with first model."""
        with patch(
            "copium_loop.utils._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = "Response from first model"

            result = await utils.invoke_gemini("Hello")

            assert result == "Response from first model"
            assert mock_exec.call_count == 1

    @pytest.mark.asyncio
    async def test_invoke_gemini_quota_fallback(self):
        """Test fallback to next model on quota error."""
        with patch(
            "copium_loop.utils._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            # Setup side effects to simulate failure then success
            mock_exec.side_effect = [
                Exception("TerminalQuotaError"),
                "Response from second model",
            ]

            result = await utils.invoke_gemini("Hello")

            assert result == "Response from second model"
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_gemini_non_quota_error_immediate_fail(self):
        """Test immediate failure on non-quota errors."""
        with patch(
            "copium_loop.utils._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.side_effect = Exception("Gemini CLI exited with code 1")

            with pytest.raises(Exception, match="Gemini CLI exited with code 1"):
                await utils.invoke_gemini("Hello")

            assert mock_exec.call_count == 1


class TestNotifications:
    """Tests for notification system."""

    @pytest.mark.asyncio
    async def test_notify_does_nothing_without_channel(self):
        """Test that notify does nothing when NTFY_CHANNEL is not set."""
        os.environ.pop("NTFY_CHANNEL", None)

        with patch("copium_loop.utils.run_command", new_callable=AsyncMock) as mock_run:
            await utils.notify("Title", "Message")
            mock_run.assert_not_called()

    @pytest.mark.asyncio
    async def test_notify_calls_curl_with_channel(self):
        """Test that notify calls curl when NTFY_CHANNEL is set."""
        os.environ["NTFY_CHANNEL"] = "test-channel"

        with (
            patch("copium_loop.utils.get_tmux_session", return_value="test-session"),
            patch("copium_loop.utils.run_command", new_callable=AsyncMock) as mock_run,
        ):
            await utils.notify("Title", "Message", 4)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][1]
            assert "Title: Title" in args
            assert "Priority: 4" in args
            assert "test-channel" in args[-1]