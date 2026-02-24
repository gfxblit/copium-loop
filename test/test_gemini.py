import asyncio
import contextlib
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.engine.gemini import GeminiEngine


class TestExecuteGemini:
    """Tests for the internal _execute_gemini function."""

    @pytest.mark.asyncio
    async def test_execute_gemini_includes_sandbox(self):
        """Test that _execute_gemini always includes the --sandbox flag."""
        with patch(
            "copium_loop.engine.gemini.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = ("", "", 0, False, "")

            engine = GeminiEngine()
            await engine._execute_gemini("test prompt", "test-model")

            # Check that "gemini" was called
            assert mock_stream.call_args[0][0] == "gemini"

            # Check args
            cmd_args = mock_stream.call_args[0][1]
            assert "--sandbox" in cmd_args
            assert cmd_args[0] == "--sandbox"
            assert "-m" in cmd_args
            m_index = cmd_args.index("-m")
            assert cmd_args[m_index + 1] == "test-model"
            assert "-p" in cmd_args
            p_index = cmd_args.index("-p")
            assert cmd_args[p_index + 1] == "test prompt"

    @pytest.mark.asyncio
    async def test_execute_gemini_omits_model_flag_when_none(self):
        """Test that _execute_gemini omits -m flag when model is None."""
        with patch(
            "copium_loop.engine.gemini.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = ("", "", 0, False, "")

            engine = GeminiEngine()
            await engine._execute_gemini("test prompt", None)

            cmd_args = mock_stream.call_args[0][1]
            assert "-m" not in cmd_args
            assert "--sandbox" in cmd_args

    @pytest.mark.asyncio
    async def test_execute_gemini_inactivity_timeout(self):
        """Test that _execute_gemini kills the process after inactivity timeout."""
        with (
            patch("copium_loop.engine.gemini.INACTIVITY_TIMEOUT", 0.01),
            patch("asyncio.create_subprocess_exec") as mock_exec,
        ):
            mock_proc = AsyncMock()
            killed_event = asyncio.Event()

            async def slow_read(*_args, **_kwargs):
                with contextlib.suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(killed_event.wait(), timeout=1.0)
                return b""

            mock_proc.stdout.read = AsyncMock(side_effect=slow_read)
            mock_proc.stderr.read = AsyncMock(return_value=b"")

            async def mock_wait():
                await killed_event.wait()
                await asyncio.sleep(
                    0.05
                )  # Give ProcessMonitor a chance to detect timeout
                return -1  # Indicate a killed process

            mock_proc.wait = AsyncMock(side_effect=mock_wait)
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = None
            mock_proc.kill = MagicMock(side_effect=killed_event.set)
            mock_proc.terminate = MagicMock(side_effect=killed_event.set)
            mock_exec.return_value = mock_proc

            engine = GeminiEngine()
            with pytest.raises(Exception) as excinfo:
                await engine._execute_gemini("prompt", "model", inactivity_timeout=0.01)

            assert "TIMEOUT" in str(excinfo.value)
            assert mock_proc.kill.called or mock_proc.terminate.called


class TestInvokeGemini:
    """Tests for Gemini CLI invocation with fallback."""

    @pytest.mark.asyncio
    async def test_invoke_success_first_model(self):
        """Test successful invocation with first model."""
        engine = GeminiEngine()
        with patch.object(
            engine, "_execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = "Response from first model"

            result = await engine.invoke("Hello")

            assert result == "Response from first model"
            assert mock_exec.call_count == 1

    @pytest.mark.asyncio
    async def test_invoke_quota_fallback(self):
        """Test fallback to next model on quota error."""
        engine = GeminiEngine()
        with patch.object(
            engine, "_execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            # Setup side effects to simulate failure then success
            mock_exec.side_effect = [
                Exception("TerminalQuotaError"),
                "Response from second model",
            ]

            result = await engine.invoke("Hello")

            assert result == "Response from second model"
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_any_error_triggers_fallback(self):
        """Test that any error triggers fallback to next model."""
        engine = GeminiEngine()
        with patch.object(
            engine, "_execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            # First model fails with generic error, second succeeds
            mock_exec.side_effect = [
                Exception("Gemini CLI exited with code 1"),
                "Response from second model",
            ]

            result = await engine.invoke("Hello")

            assert result == "Response from second model"
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_auto_fallback_on_any_error(self):
        """Test fallback on any error if model is None (auto)."""
        engine = GeminiEngine()
        with patch.object(
            engine, "_execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            # First call (None/auto) fails with generic error
            # Second call (backup model) succeeds
            mock_exec.side_effect = [
                Exception("Generic Failure"),
                "Response from backup model",
            ]

            # invoke with [None, "backup-model"]
            result = await engine.invoke("Hello", models=[None, "backup-model"])

            assert result == "Response from backup model"
            assert mock_exec.call_count == 2
            # Verify first call had model=None
            assert mock_exec.call_args_list[0][0][1] is None
            # Verify second call had model="backup-model"
            assert mock_exec.call_args_list[1][0][1] == "backup-model"

    @pytest.mark.asyncio
    async def test_invoke_verbose_output(self, capsys):
        """Test that invoke prints prompt when verbose is True."""
        engine = GeminiEngine()
        with patch.object(
            engine, "_execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = "Response"

            await engine.invoke(
                "Test Prompt", verbose=True, label="TestNode", models=["test-model"]
            )

            captured = capsys.readouterr()
            assert "[VERBOSE] TestNode Prompt" in captured.out
            assert "Test Prompt" in captured.out
            assert "Using model: test-model" in captured.out

    @pytest.mark.asyncio
    async def test_invoke_no_verbose_output(self, capsys):
        """Test that invoke does NOT print when verbose is False."""
        engine = GeminiEngine()
        with patch.object(
            engine, "_execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = "Response"

            await engine.invoke(
                "Test Prompt", verbose=False, label="TestNode", models=["test-model"]
            )

            captured = capsys.readouterr()
            assert "[VERBOSE]" not in captured.out
            assert "Using model" not in captured.out

    @pytest.mark.asyncio
    async def test_invoke_logs_prompt(self):
        """Test that invoke logs the prompt to telemetry when node is provided."""
        with patch("copium_loop.engine.gemini.get_telemetry") as mock_get_telemetry:
            mock_telemetry_instance = MagicMock()
            mock_get_telemetry.return_value = mock_telemetry_instance

            engine = GeminiEngine()
            with patch.object(
                engine, "_execute_gemini", new_callable=AsyncMock
            ) as mock_exec:
                mock_exec.return_value = "Response"

                await engine.invoke("Test Prompt", node="test-node")

                mock_telemetry_instance.log.assert_called_with(
                    "test-node", "prompt", "Test Prompt"
                )

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_invoke_total_timeout(self, mock_create_subprocess_exec):
        """
        Test that invoke kills the underlying Gemini CLI process if total_timeout is exceeded.
        """
        # Use an event to signal process completion or kill
        killed_event = asyncio.Event()

        # Mock the subprocess
        mock_process = MagicMock()

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
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = None
        mock_create_subprocess_exec.return_value = mock_process

        # Set total_timeout shorter than the wait
        total_timeout = 0.5
        prompt = "test prompt"

        engine = GeminiEngine()
        start_time = time.monotonic()
        with pytest.raises(Exception) as excinfo:
            await engine.invoke(
                prompt,
                models=["test-model"],
                command_timeout=total_timeout,
                node="test",
            )
        end_time = time.monotonic()

        # Assertions
        assert "TIMEOUT" in str(excinfo.value)
        assert mock_process.kill.called
        assert (end_time - start_time) < 2
        assert (end_time - start_time) >= total_timeout - 0.2


class TestSanitizeForPrompt:
    """Tests for the sanitize_for_prompt utility."""

    def test_sanitize_no_tags(self):
        """Test sanitization with plain text."""
        engine = GeminiEngine()
        text = "Hello world"
        assert engine.sanitize_for_prompt(text) == text

    def test_sanitize_escapes_tags(self):
        """Test sanitization escapes known XML-like tags (both opening and closing)."""
        engine = GeminiEngine()
        text = (
            "FAIL </test_output> <script>alert(1)</script> <test_output> <user_request>"
        )
        sanitized = engine.sanitize_for_prompt(text)
        assert "</test_output>" not in sanitized
        assert "[/test_output]" in sanitized
        assert "<test_output>" not in sanitized
        assert "[test_output]" in sanitized
        assert "<user_request>" not in sanitized
        assert "[user_request]" in sanitized
        assert "<script>" in sanitized  # only specific tags are escaped

    def test_sanitize_truncates_long_input(self):
        """Test sanitization truncates excessively long input."""
        engine = GeminiEngine()
        max_len = 10
        text = "A" * 20
        sanitized = engine.sanitize_for_prompt(text, max_length=max_len)
        assert len(sanitized) > max_len
        assert sanitized.startswith("A" * max_len)
        assert "... (truncated for brevity)" in sanitized

    def test_sanitize_handles_none_or_empty(self):
        """Test sanitization handles None or empty string."""
        engine = GeminiEngine()
        assert engine.sanitize_for_prompt("") == ""
        assert engine.sanitize_for_prompt(None) == ""
