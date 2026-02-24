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
