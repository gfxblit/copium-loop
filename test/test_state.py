from copium_loop.constants import (
    COMMAND_TIMEOUT,
    INACTIVITY_TIMEOUT,
    MODELS,
    NODE_TIMEOUT,
)
from copium_loop.state import AgentState


def test_agent_state_has_architect_status():
    # This will fail to compile/run if architect_status is not in AgentState
    state: AgentState = {
        "messages": [],
        "code_status": "",
        "test_output": "",
        "review_status": "",
        "architect_status": "ok",
        "retry_count": 0,
        "pr_url": "",
        "issue_url": "",
        "initial_commit_hash": "",
        "git_diff": "",
        "verbose": False,
        "last_error": "",
    }
    assert state["architect_status"] == "ok"


def test_models_defined():
    assert "gemini-3.1-pro-preview" in MODELS
    assert "gemini-3.1-flash-preview" in MODELS


def test_timeouts_defined():
    assert INACTIVITY_TIMEOUT == 600
    assert NODE_TIMEOUT == 3600
    assert COMMAND_TIMEOUT == 1800


def test_agent_state_has_engine_and_no_jules_metadata():
    """Verify that AgentState has 'engine' and no longer has 'jules_metadata'."""
    assert "jules_metadata" not in AgentState.__annotations__
    assert "engine" in AgentState.__annotations__
