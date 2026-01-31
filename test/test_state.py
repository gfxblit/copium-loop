from copium_loop.constants import ARCHITECT_MODELS
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
        "last_error": ""
    }
    assert state["architect_status"] == "ok"

def test_architect_models_defined():
    assert "gemini-2.5-pro" in ARCHITECT_MODELS
    assert "gemini-2.5-flash" in ARCHITECT_MODELS
