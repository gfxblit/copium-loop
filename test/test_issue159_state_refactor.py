from copium_loop.state import AgentState


def test_agent_state_has_engine_and_no_jules_metadata():
    """Verify that AgentState has 'engine' and no longer has 'jules_metadata'."""
    assert "jules_metadata" not in AgentState.__annotations__
    assert "engine" in AgentState.__annotations__
