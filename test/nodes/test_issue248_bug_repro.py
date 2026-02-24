from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.nodes.utils import get_coder_prompt, get_most_relevant_error


@pytest.mark.asyncio
async def test_get_most_relevant_error_prioritizes_real_error_over_infra():
    """
    Test that get_most_relevant_error correctly prioritizes a real error
    over a latest infrastructure error, to provide better context for fixing.
    """
    latest_infra_error = "All models exhausted: please try again later"
    stale_real_error = "Automatic rebase on origin/main failed with the following error: CONFLICT (content)"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=latest_infra_error),
        ],
        "last_error": stale_real_error,
    }

    error = get_most_relevant_error(state)

    # UPDATED BEHAVIOR: it picks the real error even if it's older
    assert error == stale_real_error


@pytest.mark.asyncio
async def test_get_coder_prompt_prioritizes_real_error_over_infra():
    """
    Test that get_coder_prompt correctly reports a real error even if
    a more recent infra error exists in the state.
    """
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    latest_infra_error = "All models exhausted: please try again later"
    stale_real_error = "Automatic rebase on origin/main failed with the following error: CONFLICT (content)"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=latest_infra_error),
        ],
        "review_status": "pr_failed",
        "last_error": stale_real_error,
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    # UPDATED BEHAVIOR: it reports the real failure for fixing
    assert "Your previous attempt to create a PR failed" in prompt
    assert "Automatic rebase on origin/main failed" in prompt
    assert "transient infrastructure failure" not in prompt

@pytest.mark.asyncio
async def test_get_coder_prompt_preserves_test_failure_context_on_infra_error():
    """
    Test that get_coder_prompt correctly reports the underlying test failure
    even if the current node failed due to infrastructure.
    """
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    infra_error = "All models exhausted: please try again later"
    test_failure = "FAIL test_something.py: Expected 1 but got 2"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=infra_error)
        ],
        "code_status": "failed",
        "test_output": test_failure,
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    # It should mention the test failure, not just 'retry on original prompt'
    assert "Your previous implementation failed tests" in prompt
    assert test_failure in prompt
