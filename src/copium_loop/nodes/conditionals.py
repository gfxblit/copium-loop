from langgraph.graph import END

from copium_loop.constants import MAX_RETRIES
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


def should_continue_from_test(state: AgentState) -> str:
    telemetry = get_telemetry()
    if state.get("test_output") == "PASS":
        telemetry.log_status("tester", "success")
        return "reviewer"

    if state.get("retry_count", 0) > MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("tester", "error")
        return END

    return "coder"


def should_continue_from_review(state: AgentState) -> str:
    telemetry = get_telemetry()
    if state.get("review_status") == "approved":
        telemetry.log_status("reviewer", "success")
        return "pr_creator"

    if state.get("retry_count", 0) > MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("reviewer", "error")
        return END

    return "coder"


def should_continue_from_pr_creator(state: AgentState) -> str:
    telemetry = get_telemetry()
    status = state.get("review_status")
    if status in ["pr_created", "pr_skipped"]:
        telemetry.log_status("pr_creator", "success")
        return END

    if state.get("retry_count", 0) > MAX_RETRIES:
        print("Max retries exceeded in PR Creator. Aborting.")
        telemetry.log_status("pr_creator", "error")
        return END

    print(f"PR Creator failed or needs commit (status: {status}). Returning to coder.")
    return "coder"
