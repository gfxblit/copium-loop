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

        with pytest.raises(ValueError, match="Something went wrong"):
            await failing_node(state)

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

    # Non-infrastructure errors
    assert is_infrastructure_error("SyntaxError: invalid syntax") is False
    assert is_infrastructure_error("AssertionError: assert False") is False
    assert is_infrastructure_error("ValueError: invalid value") is False
    assert is_infrastructure_error("") is False
