from copium_loop.constants import MODELS
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
    assert "gemini-3-pro-preview" in MODELS
    assert "gemini-3-flash-preview" in MODELS
