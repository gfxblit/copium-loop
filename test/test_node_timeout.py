import asyncio
from unittest.mock import patch

import pytest

from copium_loop.copium_loop import WorkflowManager


@pytest.mark.asyncio
async def test_node_timeout_wrapping():
    """
    Test that WorkflowManager._wrap_node correctly times out a slow node.
    """

    async def slow_node(_state):
        await asyncio.sleep(2)
        return {"test_output": "PASS"}

    manager = WorkflowManager()

    # Mock NODE_TIMEOUT to 0.1s for testing
    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):
        wrapped = manager._wrap_node("slow_node", slow_node)
        state = {"retry_count": 0}
        result = await wrapped(state)

        assert result["retry_count"] == 1
        # The node name in wrapper is obtained via node_name argument
        # For our local slow_node, it's "slow_node"
        # Since it's not "tester", "reviewer" etc, it should return default {"retry_count": 1}
        assert "test_output" not in result


@pytest.mark.asyncio
async def test_tester_node_timeout():
    """
    Test that WorkflowManager._wrap_node correctly handles a timeout for the tester node.
    """

    async def tester(_state):
        await asyncio.sleep(2)
        return {"test_output": "PASS"}

    manager = WorkflowManager()

    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):
        wrapped = manager._wrap_node("tester", tester)
        state = {"retry_count": 5}
        result = await wrapped(state)

        assert result["retry_count"] == 6
        assert "FAIL: Node 'tester' timed out" in result["test_output"]


@pytest.mark.asyncio
async def test_reviewer_node_timeout():
    """
    Test that WorkflowManager._wrap_node correctly handles a timeout for the reviewer node.
    """

    async def reviewer(_state):
        await asyncio.sleep(2)
        return {"review_status": "approved"}

    manager = WorkflowManager()

    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):
        wrapped = manager._wrap_node("reviewer", reviewer)
        state = {"retry_count": 2}
        result = await wrapped(state)

        assert result["retry_count"] == 3
        assert result["review_status"] == "error"
        assert "Node 'reviewer' timed out" in result["messages"][0].content


@pytest.mark.asyncio
async def test_default_node_timeout():
    """
    Test that WorkflowManager._wrap_node returns a default error state for unknown nodes.
    """

    async def unknown_node(_state):
        await asyncio.sleep(2)
        return {"foo": "bar"}

    manager = WorkflowManager()

    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):
        wrapped = manager._wrap_node("unknown_node", unknown_node)
        state = {"retry_count": 0}
        result = await wrapped(state)

        assert result["retry_count"] == 1
        assert "error" in result
        assert "Node 'unknown_node' timed out" in result["error"]
