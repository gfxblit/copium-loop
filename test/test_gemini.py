from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import gemini


class TestExecuteGemini:
    """Tests for the internal _execute_gemini function."""

    @pytest.mark.asyncio
    async def test_execute_gemini_includes_sandbox(self):
        """Test that _execute_gemini always includes the --sandbox flag."""
        with patch(
            "copium_loop.gemini.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = ("", 0, False, "")

            await gemini._execute_gemini("test prompt", "test-model")

            # Check that "gemini" was called
            assert mock_stream.call_args[0][0] == "gemini"

            # Check args
            cmd_args = mock_stream.call_args[0][1]
            assert "--sandbox" in cmd_args
            assert cmd_args[0] == "--sandbox"
            assert "-m" in cmd_args
            m_index = cmd_args.index("-m")
            assert cmd_args[m_index + 1] == "test-model"

    @pytest.mark.asyncio
    async def test_execute_gemini_omits_model_flag_when_none(self):
        """Test that _execute_gemini omits -m flag when model is None."""
        with patch(
            "copium_loop.gemini.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream:
            mock_stream.return_value = ("", 0, False, "")

            await gemini._execute_gemini("test prompt", None)

            cmd_args = mock_stream.call_args[0][1]
            assert "-m" not in cmd_args
            assert "--sandbox" in cmd_args


class TestInvokeGemini:
    """Tests for Gemini CLI invocation with fallback."""

    @pytest.mark.asyncio
    async def test_invoke_gemini_success_first_model(self):
        """Test successful invocation with first model."""
        with patch(
            "copium_loop.gemini._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = "Response from first model"

            result = await gemini.invoke_gemini("Hello")

            assert result == "Response from first model"
            assert mock_exec.call_count == 1

    @pytest.mark.asyncio
    async def test_invoke_gemini_quota_fallback(self):
        """Test fallback to next model on quota error."""
        with patch(
            "copium_loop.gemini._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            # Setup side effects to simulate failure then success
            mock_exec.side_effect = [
                Exception("TerminalQuotaError"),
                "Response from second model",
            ]

            result = await gemini.invoke_gemini("Hello")

            assert result == "Response from second model"
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_gemini_any_error_triggers_fallback(self):
        """Test that any error triggers fallback to next model."""
        with patch(
            "copium_loop.gemini._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            # First model fails with generic error, second succeeds
            mock_exec.side_effect = [
                Exception("Gemini CLI exited with code 1"),
                "Response from second model",
            ]

            result = await gemini.invoke_gemini("Hello")

            assert result == "Response from second model"
            assert mock_exec.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_gemini_auto_fallback_on_any_error(self):
        """Test fallback on any error if model is None (auto)."""
        with patch(
            "copium_loop.gemini._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            # First call (None/auto) fails with generic error
            # Second call (backup model) succeeds
            mock_exec.side_effect = [
                Exception("Generic Failure"),
                "Response from backup model",
            ]

            # invoke with [None, "backup-model"]
            result = await gemini.invoke_gemini("Hello", models=[None, "backup-model"])

            assert result == "Response from backup model"
            assert mock_exec.call_count == 2
            # Verify first call had model=None
            assert mock_exec.call_args_list[0][0][1] is None
            # Verify second call had model="backup-model"
            assert mock_exec.call_args_list[1][0][1] == "backup-model"

    @pytest.mark.asyncio
    async def test_invoke_gemini_verbose_output(self, capsys):
        """Test that invoke_gemini prints prompt when verbose is True."""
        with patch(
            "copium_loop.gemini._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = "Response"

            await gemini.invoke_gemini(
                "Test Prompt", verbose=True, label="TestNode", models=["test-model"]
            )

            captured = capsys.readouterr()
            assert "[VERBOSE] TestNode Prompt" in captured.out
            assert "Test Prompt" in captured.out
            assert "Using model: test-model" in captured.out

    @pytest.mark.asyncio
    async def test_invoke_gemini_no_verbose_output(self, capsys):
        """Test that invoke_gemini does NOT print when verbose is False."""
        with patch(
            "copium_loop.gemini._execute_gemini", new_callable=AsyncMock
        ) as mock_exec:
            mock_exec.return_value = "Response"

            await gemini.invoke_gemini(
                "Test Prompt", verbose=False, label="TestNode", models=["test-model"]
            )

            captured = capsys.readouterr()
            assert "[VERBOSE]" not in captured.out
            assert "Using model" not in captured.out
