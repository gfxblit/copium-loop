import asyncio
from unittest.mock import patch

import pytest

from copium_loop.copium_loop import WorkflowManager


@pytest.mark.asyncio
async def test_node_timeout_with_retry():
    """Test that nodes time out and increment retry_count."""

    async def slow_node(_state):
        await asyncio.sleep(2)
        return {"test_output": "PASS"}

    manager = WorkflowManager()
    # Mock NODE_TIMEOUT to be very short
    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):
        wrapped = manager._wrap_node("tester", slow_node)
        state = {"retry_count": 0}
        result = await wrapped(state)

        assert result["retry_count"] == 1
        assert "FAIL: Node 'tester' timed out" in result["test_output"]


@pytest.mark.asyncio
async def test_node_timeout_error_status():
    """Test that non-tester nodes time out and set error/rejected status."""

    async def slow_coder(_state):
        await asyncio.sleep(2)
        return {"code_status": "coded"}

    manager = WorkflowManager()
    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):
        wrapped = manager._wrap_node("coder", slow_coder)
        state = {"retry_count": 0}
        result = await wrapped(state)

        assert result["retry_count"] == 1
        assert result["code_status"] == "failed"
        assert result["review_status"] == "rejected"
        assert "Node 'coder' timed out" in result["messages"][0].content


@pytest.mark.asyncio
async def test_node_timeout_reviewer():
    """Test that reviewer node times out and sets error status."""

    async def slow_reviewer(_state):
        await asyncio.sleep(2)
        return {"review_status": "approved"}

    manager = WorkflowManager()
    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):
        wrapped = manager._wrap_node("reviewer", slow_reviewer)
        state = {"retry_count": 0}
        result = await wrapped(state)

        assert result["retry_count"] == 1
        assert result["review_status"] == "error"
        assert "Node 'reviewer' timed out" in result["messages"][0].content


@pytest.mark.asyncio
async def test_node_timeout_pr_creator():
    """Test that pr_creator node times out and sets pr_failed status."""

    async def slow_pr_creator(_state):
        await asyncio.sleep(2)
        return {"review_status": "pr_created"}

    manager = WorkflowManager()
    with patch("copium_loop.copium_loop.NODE_TIMEOUT", 0.1):
        wrapped = manager._wrap_node("pr_creator", slow_pr_creator)
        state = {"retry_count": 0}
        result = await wrapped(state)

        assert result["retry_count"] == 1
        assert result["review_status"] == "pr_failed"
        assert "Node 'pr_creator' timed out" in result["messages"][0].content


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
        assert "last_error" in result
        assert "Node 'unknown_node' timed out" in result["last_error"]


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
