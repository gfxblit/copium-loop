from unittest.mock import patch

import pytest

from copium_loop.nodes.utils import node_header


@pytest.mark.asyncio
async def test_node_header_decorator(capsys):
    """Test that the node_header decorator prints and logs correctly."""

    @node_header("test_node")
    async def mock_node(_state):
        return {"result": "ok"}

    state = {}
    with patch("copium_loop.nodes.utils.get_telemetry") as mock_get_telemetry:
        mock_telemetry = mock_get_telemetry.return_value

        result = await mock_node(state)

        # Check return value
        assert result == {"result": "ok"}

        # Check telemetry calls
        mock_telemetry.log_status.assert_called_with("test_node", "active")

        # Check printed output
        captured = capsys.readouterr()
        assert "--- Test Node ---" in captured.out

        # Check log_info call
        expected_msg = "\n--- Test Node ---\n"
        mock_telemetry.log_info.assert_called_with("test_node", expected_msg)


@pytest.mark.asyncio
async def test_node_header_with_special_naming(capsys):
    """Test that the node_header decorator handles special names correctly."""

    @node_header("pr_pre_checker")
    async def mock_node(_state):
        return {"result": "ok"}

    state = {}
    with patch("copium_loop.nodes.utils.get_telemetry"):
        await mock_node(state)

        # Check printed output - should be formatted nicely
        captured = capsys.readouterr()
        assert "--- PR Pre-Checker Node ---" in captured.out


@pytest.mark.asyncio
async def test_node_header_exception_handling():
    """Test that the node_header decorator logs failure status on exception."""

    @node_header("error_node")
    async def failing_node(_state):
        raise ValueError("Something went wrong")

    state = {}
    with patch("copium_loop.nodes.utils.get_telemetry") as mock_get_telemetry:
        mock_telemetry = mock_get_telemetry.return_value

        result = await failing_node(state)

        # Check that it returns the error status from handle_node_error
        assert result["node_status"] == "error"
        assert "Something went wrong" in result["last_error"]

        # Should have logged active, then failed
        mock_telemetry.log_status.assert_any_call("error_node", "active")
        mock_telemetry.log_status.assert_any_call("error_node", "failed")


def test_is_infrastructure_error():
    from copium_loop.nodes.utils import is_infrastructure_error

    # Git/Network errors
    assert is_infrastructure_error("Could not resolve host: github.com") is True
    assert (
        is_infrastructure_error("fatal: unable to access 'https://github.com/...'")
        is True
    )
    assert is_infrastructure_error("Connection refused") is True
    assert is_infrastructure_error("Operation timed out") is True
    assert is_infrastructure_error("Network is unreachable") is True

    # Model exhaustion
    assert is_infrastructure_error("all models exhausted") is True
    assert is_infrastructure_error("All models exhausted in Jules session") is True


@pytest.mark.asyncio
async def test_get_coder_prompt_filters_infra_errors():
    from unittest.mock import MagicMock

    from langchain_core.messages import HumanMessage

    from copium_loop.nodes.utils import get_coder_prompt

    engine = MagicMock()
    engine.sanitize_for_prompt.side_effect = lambda x: x

    # Case 1: Infrastructure error in code_status == failed
    state = {
        "messages": [HumanMessage(content="test prompt")],
        "code_status": "failed",
        "last_error": "fatal: unable to access 'https://github.com/...' ",
        "retry_count": 1,
    }

    prompt = await get_coder_prompt("gemini", state, engine)
    assert "fatal: unable to access" not in prompt
    assert "<error>" not in prompt
    assert "Coder encountered a transient infrastructure failure" in prompt

    # Case 2: Normal error in code_status == failed
    state = {
        "messages": [HumanMessage(content="test prompt")],
        "code_status": "failed",
        "last_error": "SyntaxError: invalid syntax",
        "retry_count": 1,
    }

    prompt = await get_coder_prompt("gemini", state, engine)
    assert "SyntaxError: invalid syntax" in prompt
    assert "<error>" in prompt

    # Case 3: Infrastructure error in review_status == pr_failed
    state = {
        "messages": [HumanMessage(content="test prompt")],
        "review_status": "pr_failed",
        "last_error": "Connection refused",
        "retry_count": 1,
    }

    prompt = await get_coder_prompt("gemini", state, engine)
    assert "Connection refused" not in prompt
    assert "<error>" not in prompt
    assert (
        "PR failed encountered a transient infrastructure failure" in prompt
        or "attempt to create a PR encountered a transient infrastructure failure"
        in prompt
    )

    # Case 4: Normal error in review_status == pr_failed
    state = {
        "messages": [HumanMessage(content="test prompt")],
        "review_status": "pr_failed",
        "last_error": "github branch already exists",
        "retry_count": 1,
    }

    prompt = await get_coder_prompt("gemini", state, engine)
    assert "github branch already exists" in prompt
    assert "<error>" in prompt
