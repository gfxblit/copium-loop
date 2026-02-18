from copium_loop.state import AgentState


def test_agent_state_has_no_engine_and_has_jules_metadata():
    """Verify that AgentState no longer has 'engine' and has 'jules_metadata'."""
    assert "jules_metadata" in AgentState.__annotations__
    assert "engine" not in AgentState.__annotations__
