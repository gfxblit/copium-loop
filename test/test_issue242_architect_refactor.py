from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.nodes.conditionals import (
    should_continue_from_architect,
    should_continue_from_test,
)
from copium_loop.nodes.utils import get_coder_prompt


@pytest.mark.asyncio
async def test_get_coder_prompt_filters_infra_error_in_test_output():
    """
    Architectural Issue 3: get_coder_prompt should filter out infra errors
    even if they are in test_output.
    """
    mock_engine = MagicMock()
    mock_engine.sanitize_for_prompt.side_effect = lambda x: x

    infra_error = "fatal: unable to access 'https://github.com/...' "
    state = {
        "messages": [HumanMessage(content="Implement feature X")],
        "test_output": f"FAIL: {infra_error}",
        "code_status": "coded",
        "retry_count": 1,
        "last_error": infra_error,
    }

    prompt = await get_coder_prompt("gemini", state, mock_engine)

    # It should NOT contain the infra error message
    assert infra_error not in prompt
    # It should indicate a transient failure
    assert "transient infrastructure failure" in prompt.lower()


def test_should_continue_from_architect_realistic_infra_error():
    """
    Architectural Issue 1 & 2: Test transition when architect fails with an exception.
    In this case, architect_status will be 'error' (set by _handle_error).
    """
    infra_error = "fatal: unable to access 'https://github.com/...' "
    state = {
        "architect_status": "error",  # Set by _handle_error when architect node raises Exception
        "last_error": infra_error,
        "retry_count": 1,
    }

    # It should retry architect, not go to END or coder (if it's a transient error)
    # Actually, current implementation returns 'architect' for status == 'error'.
    assert should_continue_from_architect(state) == "architect"


def test_should_continue_from_architect_unset_status():
    """
    Architectural Issue 1: If architect_status is unset (None), what happens?
    The architect says it defaults to END. Let's verify.
    """
    state = {"architect_status": None, "retry_count": 1}
    # If it defaults to END, this will fail if we want it to retry.
    assert should_continue_from_architect(state) != "END"
    # Actually, let's see what it DOES return.
    result = should_continue_from_architect(state)
    assert result in ["architect", "coder"]


def test_should_continue_from_test_realistic_infra_error():
    """
    If tester fails with infra error, it currently goes to 'coder'.
    But maybe it should retry 'tester'?
    The architect says 'leaving the state machine vulnerable'.
    If it goes to coder, the coder will see 'transient infrastructure failure' and retry.
    """
    infra_error = "fatal: unable to access 'https://github.com/...' "
    state = {
        "test_output": f"FAIL: {infra_error}",
        "last_error": infra_error,
        "retry_count": 1,
    }

    # Current behavior:
    assert should_continue_from_test(state) == "coder"
    # If we want it to retry tester, it should be 'tester'.
    # But let's see what the plan says.
