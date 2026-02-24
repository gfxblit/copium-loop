import pytest

from copium_loop.nodes.utils import node_header
from copium_loop.state import AgentState


@pytest.mark.asyncio
async def test_node_header_metadata():
    """Test that node_header correctly attaches metadata to the wrapped function."""

    @node_header("test_node", status_key="test_status", error_value="test_error")
    async def my_node(_state: AgentState):
        return {"foo": "bar"}

    assert my_node._node_name == "test_node"
    assert my_node._status_key == "test_status"
    assert my_node._error_value == "test_error"


@pytest.mark.asyncio
async def test_node_header_default_metadata():
    """Test that node_header uses defaults for metadata."""

    @node_header("test_node")
    async def my_node(_state: AgentState):
        return {"foo": "bar"}

    assert my_node._node_name == "test_node"
    assert my_node._status_key is None
    assert my_node._error_value == "error"
