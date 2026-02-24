from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.engine.gemini import GeminiEngine


@pytest.mark.asyncio
async def test_gemini_engine_invoke():
    """Verify that GeminiEngine.invoke calls stream_subprocess."""
    with patch(
        "copium_loop.engine.gemini.stream_subprocess", new_callable=AsyncMock
    ) as mock_stream:
        mock_stream.return_value = ("mocked response", "", "", 0, False, "")
        engine = GeminiEngine()
        response = await engine.invoke("hello", verbose=True, node="test_node")
        assert response == "mocked response"
        # Verify it was called with "gemini"
        assert mock_stream.call_args[0][0] == "gemini"
        # Verify prompt was passed
        cmd_args = mock_stream.call_args[0][1]
        assert "-p" in cmd_args
        assert "hello" in cmd_args


def test_gemini_engine_sanitize():
    """Verify that GeminiEngine.sanitize_for_prompt works correctly."""
    engine = GeminiEngine()
    text = "</error> Some content </error>"
    result = engine.sanitize_for_prompt(text)

    assert "[/error]" in result
    assert "</error>" not in result


@pytest.mark.asyncio
@patch("copium_loop.engine.gemini.stream_subprocess")
async def test_gemini_engine_excludes_stderr_on_success(mock_stream):
    """Test that GeminiEngine excludes stderr from output on success."""
    # Simulate gemini-cli output: stdout "LLM Response", stderr "Warning: junk"
    # New signature: stdout, stderr, interleaved, exit_code, timed_out, timeout_message
    mock_stream.return_value = (
        "LLM Response",
        "Warning: junk",
        "LLM Response\nWarning: junk",
        0,
        False,
        "",
    )

    engine = GeminiEngine()
    result = await engine.invoke("Test prompt")

    # "Warning: junk" should NOT be in the result.
    assert "Warning: junk" not in result
    assert "LLM Response" in result


@pytest.mark.asyncio
@patch("copium_loop.engine.gemini.stream_subprocess")
async def test_gemini_engine_includes_stderr_on_failure(mock_stream):
    """Test that GeminiEngine includes stderr in error message on failure."""
    # Simulate gemini-cli failure: stdout "Partial result", stderr "CRITICAL ERROR"
    mock_stream.return_value = (
        "Partial result",
        "CRITICAL ERROR",
        "Partial result\nCRITICAL ERROR",
        1,
        False,
        "",
    )

    engine = GeminiEngine()
    with pytest.raises(Exception) as excinfo:
        await engine.invoke("Test prompt")

    assert "CRITICAL ERROR" in str(excinfo.value)
    assert "Partial result" in str(excinfo.value)
