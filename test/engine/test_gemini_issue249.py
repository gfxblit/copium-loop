from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.engine.gemini import GeminiEngine


@pytest.mark.asyncio
async def test_gemini_engine_filters_stderr_on_success():
    """
    Verify that GeminiEngine.invoke returns only stdout on success,
    filtering out any noise from stderr.
    """
    with patch(
        "copium_loop.engine.gemini.stream_subprocess", new_callable=AsyncMock
    ) as mock_stream:
        # Mock returns (stdout, stderr, interleaved, exit_code, timed_out, timeout_message)
        mock_stream.return_value = (
            "clean response",
            "noisy warning",
            "clean responsenoisy warning",
            0,
            False,
            "",
        )

        engine = GeminiEngine()
        response = await engine.invoke("hello", node="test_node")

        # Current implementation would return "clean responsenoisy warning" (depending on how it was updated)
        # We want it to be just "clean response"
        assert response == "clean response"


@pytest.mark.asyncio
async def test_gemini_engine_includes_stderr_on_failure():
    """
    Verify that GeminiEngine includes both stdout and stderr in the exception on failure.
    """
    with patch(
        "copium_loop.engine.gemini.stream_subprocess", new_callable=AsyncMock
    ) as mock_stream:
        mock_stream.return_value = (
            "stdout content",
            "stderr content",
            "interleaved content",
            1,
            False,
            "",
        )

        engine = GeminiEngine()
        with pytest.raises(Exception) as excinfo:
            await engine.invoke("hello")

        assert "stdout content" in str(excinfo.value)
        assert "stderr content" in str(excinfo.value)
        assert "exited with code 1" in str(excinfo.value)
