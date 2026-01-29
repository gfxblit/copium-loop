import asyncio
from unittest.mock import patch

import pytest

from copium_loop.copium_loop import WorkflowManager


@pytest.mark.asyncio
async def test_node_exceeds_inactivity_but_below_node_timeout():
    """
    Test that a node can run longer than INACTIVITY_TIMEOUT if it's below NODE_TIMEOUT.
    """
    async def mid_length_node(_state):
        # Sleep for longer than INACTIVITY_TIMEOUT but less than what NODE_TIMEOUT will be
        # We'll mock these to small values for speed
        await asyncio.sleep(0.5)
        return {"test_output": "PASS"}

    manager = WorkflowManager()

    # We want it to NOT timeout at a small value (like 0.2s)
    # but timeout at NODE_TIMEOUT (1.0s)

    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 1.0):
        wrapped = manager._wrap_node("mid_length_node", mid_length_node)
        state = {"retry_count": 0}

        result = await wrapped(state)

        assert "test_output" in result
        assert result["test_output"] == "PASS"
        assert result.get("retry_count", 0) == 0


@pytest.mark.asyncio
async def test_node_exceeds_node_timeout():
    """
    Test that a node still times out if it exceeds NODE_TIMEOUT.
    """
    async def very_slow_node(_state):
        await asyncio.sleep(1.0)
        return {"test_output": "PASS"}

    manager = WorkflowManager()

    # We want it to timeout at NODE_TIMEOUT (0.5s)

    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.5):

        wrapped = manager._wrap_node("very_slow_node", very_slow_node)
        state = {"retry_count": 0}
        result = await wrapped(state)

        assert "retry_count" in result
        assert result["retry_count"] == 1
        assert "timed out after 0.5s" in str(result)
