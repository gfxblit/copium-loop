from langgraph.graph import END

from copium_loop.state import AgentState


def should_continue_from_test(state: AgentState) -> str:
    if state.get("test_output") == "PASS":
        return "reviewer"

    if state.get("retry_count", 0) > 3:
        print("Max retries exceeded. Aborting.")
        return END

    return "coder"


def should_continue_from_review(state: AgentState) -> str:
    if state.get("review_status") == "approved":
        return "pr_creator"

    if state.get("retry_count", 0) > 3:
        print("Max retries exceeded. Aborting.")
        return END

    return "coder"


def should_continue_from_pr_creator(state: AgentState) -> str:
    status = state.get("review_status")
    if status in ["pr_created", "pr_skipped"]:
        return END

    if state.get("retry_count", 0) > 3:
        print("Max retries exceeded in PR Creator. Aborting.")
        return END

    print(f"PR Creator failed or needs commit (status: {status}). Returning to coder.")
    return "coder"
