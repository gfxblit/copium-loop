from langgraph.graph import END

from copium_loop import constants
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


def should_continue_from_test(state: AgentState) -> str:
    telemetry = get_telemetry()

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("tester", "error")
        telemetry.log_workflow_status("failed")
        return END

    if state.get("node_status") == "infra_error":
        return "tester"

    if state.get("test_output") == "PASS":
        telemetry.log_status("tester", "success")
        return "architect"

    telemetry.log_status("tester", "failed")
    return "coder"


def should_continue_from_architect(state: AgentState) -> str:
    telemetry = get_telemetry()

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("architect", "error")
        telemetry.log_workflow_status("failed")
        return END

    if state.get("node_status") == "infra_error":
        return "architect"

    status = state.get("architect_status")

    if status == "approved":
        telemetry.log_status("architect", "success")
        return "reviewer"

    telemetry.log_status("architect", status if status else "error")
    if status == "error":
        return "architect"

    # Verdict: rejected returns to coder
    return "coder"


def should_continue_from_review(state: AgentState) -> str:
    telemetry = get_telemetry()

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("reviewer", "error")
        telemetry.log_workflow_status("failed")
        return END

    if state.get("node_status") == "infra_error":
        return "reviewer"

    status = state.get("review_status")

    if status == "approved":
        telemetry.log_status("reviewer", "success")
        return "pr_pre_checker"

    telemetry.log_status("reviewer", status if status else "error")
    if status == "error":
        return "reviewer"

    if status == "pr_failed":
        return "pr_failed"

    # Verdict: rejected returns to coder
    return "coder"


def should_continue_from_pr_creator(state: AgentState) -> str:
    telemetry = get_telemetry()

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded in PR Creator. Aborting.")
        telemetry.log_status("pr_creator", "error")
        telemetry.log_workflow_status("failed")
        return END

    if state.get("node_status") == "infra_error":
        return "pr_creator"

    status = state.get("review_status")

    if status == "pr_created":
        telemetry.log_status("pr_creator", "success")
        return END

    if status == "pr_skipped":
        telemetry.log_status("pr_creator", "success")
        return END

    print(
        f"PR Creator failed or needs commit (status: {repr(status)}). Returning to coder."
    )
    telemetry.log_status("pr_creator", "failed")
    return "coder"


def should_continue_from_pr_pre_checker(state: AgentState) -> str:
    telemetry = get_telemetry()

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded in PR Pre-Checker. Aborting.")
        telemetry.log_status("pr_pre_checker", "error")
        telemetry.log_workflow_status("failed")
        return END

    if state.get("node_status") == "infra_error":
        return "pr_pre_checker"

    status = state.get("review_status")

    if status == "pre_check_passed":
        telemetry.log_status("pr_pre_checker", "success")
        return "pr_creator"

    if status == "pr_skipped":
        telemetry.log_status("pr_pre_checker", "success")
        return END

    print(
        f"PR Pre-Checker failed or needs commit (status: {repr(status)}). Returning to coder."
    )
    telemetry.log_status("pr_pre_checker", "failed")
    return "coder"


def should_continue_from_journaler(state: AgentState) -> str:
    telemetry = get_telemetry()

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        # Journaler usually doesn't fail in a way that needs retries, but for consistency:
        return END

    if state.get("node_status") == "infra_error":
        return "journaler"

    telemetry.log_status("journaler", "success")
    status = state.get("review_status")

    if status == "pre_check_passed":
        return "pr_creator"
    return END


def should_continue_from_coder(state: AgentState) -> str:
    telemetry = get_telemetry()

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded from coder. Aborting.")
        telemetry.log_status("coder", "error")
        telemetry.log_workflow_status("failed")
        return END

    if state.get("node_status") == "infra_error":
        return "coder"

    status = state.get("code_status")

    if status == "coded":
        telemetry.log_status("coder", "success")
        return "tester"

    print(f"Coder failed (status: {repr(status)}). Retrying...")
    telemetry.log_status("coder", "failed")
    return "coder"
