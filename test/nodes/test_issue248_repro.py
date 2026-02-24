from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.nodes.utils import get_coder_prompt, get_most_relevant_error


@pytest.mark.asyncio
async def test_get_coder_prompt_repro_issue_248():
    """
    Reproduction for Issue 248:
    Simulate a workflow state where last_error contains a stale infra error string.
    Set review_status to pr_failed and add a SystemMessage with a rebase conflict.
    Assert that get_coder_prompt correctly selects the rebase conflict, NOT the infra error.
    """
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    # Stale infra error in last_error
    stale_infra_error = "All models exhausted: please try again later"

    # New rebase conflict in a SystemMessage
    rebase_conflict = "Automatic rebase on origin/main failed with the following error: CONFLICT (content): Merge conflict in file.py"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=rebase_conflict),
        ],
        "review_status": "pr_failed",
        "last_error": stale_infra_error,
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    assert "Automatic rebase on origin/main failed" in prompt
    assert "CONFLICT (content)" in prompt
    assert "Infrastructure error" not in prompt


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
            SystemMessage(content=infra_error),
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


@pytest.mark.asyncio
async def test_get_most_relevant_error_stale_real_error():
    """
    Test that get_most_relevant_error prioritizes a real error even if it's older
    than an infrastructure error.
    """
    infra_error = "All models exhausted: please try again later"
    real_error = "Automatic rebase on origin/main failed with the following error: CONFLICT (content)"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=real_error),
            SystemMessage(content=infra_error),
        ],
        "last_error": infra_error,
    }

    error = get_most_relevant_error(state)
    assert error == real_error


@pytest.mark.asyncio
async def test_get_coder_prompt_misreports_infra_error():
    """
    Test that get_coder_prompt should NOT report infra error if a real error
    occurred previously that needs fixing.
    """
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    infra_error = "All models exhausted: please try again later"
    real_error = "Automatic rebase on origin/main failed with the following error: CONFLICT (content)"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=real_error),
            SystemMessage(content=infra_error),
        ],
        "review_status": "pr_failed",
        "last_error": infra_error,
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    # It should mention the real failure, not just retry on infra
    assert "Your previous attempt to create a PR failed" in prompt
    assert real_error in prompt
    assert "transient infrastructure failure" not in prompt


@pytest.mark.asyncio
async def test_get_most_relevant_error_prioritizes_latest():
    """
    Test that get_most_relevant_error still prioritizes the latest if both are real.
    """
    error1 = "Error 1: something went wrong"
    error2 = "Error 2: something else went wrong"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=error1),
            SystemMessage(content=error2),
        ],
        "last_error": error1,
    }

    error = get_most_relevant_error(state)
    assert error == error2


@pytest.mark.asyncio
async def test_get_coder_prompt_correctly_reports_infra_error_if_no_real_error():
    """
    Test that if ONLY infra errors exist, it correctly reports infra error.
    """
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    infra_error = "All models exhausted: please try again later"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=infra_error),
        ],
        "review_status": "pr_failed",
        "last_error": infra_error,
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    assert "transient infrastructure failure" in prompt


@pytest.mark.asyncio
async def test_get_coder_prompt_prioritizes_real_error_over_infra_test_output():
    """
    Test that get_coder_prompt prioritizes a real error in message history
    even if the latest test_output is an infrastructure error.
    """
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    infra_error = "All models exhausted: please try again later"
    real_error = "FAIL test_something.py: Expected 1 but got 2"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=real_error),
            SystemMessage(content=infra_error),
        ],
        "test_output": "FAIL (Unit tests):\n" + infra_error,
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    # It should mention the real failure
    assert "Your previous implementation failed tests" in prompt
    assert real_error in prompt
    assert "transient infrastructure failure" not in prompt


@pytest.mark.asyncio
async def test_get_coder_prompt_prioritizes_real_error_over_infra_pr_failed():
    """
    Test that get_coder_prompt prioritizes a real error in message history
    even if the latest error during PR creation is an infrastructure error.
    """
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    infra_error = "All models exhausted: please try again later"
    real_error = "fatal: A branch named 'feature-1' already exists."

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=real_error),
            SystemMessage(content=infra_error),
        ],
        "review_status": "pr_failed",
        "last_error": infra_error,
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    # It should mention the real failure
    assert "Your previous attempt to create a PR failed" in prompt
    assert real_error in prompt
    assert "transient infrastructure failure" not in prompt
