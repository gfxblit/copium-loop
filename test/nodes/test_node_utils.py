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
