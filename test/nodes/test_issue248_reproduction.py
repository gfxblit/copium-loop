from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.engine.gemini import GeminiEngine
from copium_loop.nodes.utils import get_coder_prompt


@pytest.mark.asyncio
async def test_get_coder_prompt_handles_review_refactor():
    """Test that get_coder_prompt handles review_status='refactor' correctly."""
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    state = {
        "messages": [HumanMessage(content="Original request")],
        "review_status": "refactor",
        "last_error": "Code is correct but needs refactoring for better readability.",
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    # It should mention it was flagged for refactor by the reviewer.
    assert "flagged for refactoring by the reviewer" in prompt
    assert "Code is correct but needs refactoring" in prompt


@pytest.mark.asyncio
@patch("copium_loop.engine.gemini.stream_subprocess")
async def test_gemini_engine_excludes_stderr_on_success(mock_stream):
    """Test that GeminiEngine excludes stderr from output on success."""
    # Simulate gemini-cli output: stdout "LLM Response", stderr "Warning: junk"
    # New signature: stdout, stderr, exit_code, timed_out, timeout_message
    mock_stream.return_value = ("LLM Response", "Warning: junk", 0, False, "")

    engine = GeminiEngine()
    result = await engine.invoke("Test prompt")

    # If the fix is implemented, "Warning: junk" should NOT be in the result.
    assert "Warning: junk" not in result
    assert "LLM Response" in result


@pytest.mark.asyncio
@patch("copium_loop.engine.gemini.stream_subprocess")
async def test_gemini_engine_includes_stderr_on_failure(mock_stream):
    """Test that GeminiEngine includes stderr in error message on failure."""
    # Simulate gemini-cli failure: stdout "Partial result", stderr "CRITICAL ERROR"
    mock_stream.return_value = ("Partial result", "CRITICAL ERROR", 1, False, "")

    engine = GeminiEngine()
    with pytest.raises(Exception) as excinfo:
        await engine.invoke("Test prompt")

    assert "CRITICAL ERROR" in str(excinfo.value)
    assert "Partial result" in str(excinfo.value)
