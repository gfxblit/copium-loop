from langgraph.graph import END

from copium_loop import constants
from copium_loop.nodes.utils import is_infrastructure_error
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


def _check_infra_error(state: AgentState, telemetry, node: str) -> str | None:
    """Centralized check for infrastructure errors."""
    last_error = state.get("last_error")
    # Only fail if it's an infra error AND it happened in THIS node
    if (
        last_error
        and is_infrastructure_error(last_error)
        and f"Node '{node}'" in last_error
    ):
        print(f"\nInfrastructure failure detected in {node}: {last_error}")
        print("Terminating workflow to prevent futile retries.")
        telemetry.log_status(node, "failed")
        telemetry.log_workflow_status("failed")
        return END
    return None


def should_continue_from_test(state: AgentState) -> str:
    telemetry = get_telemetry()
    if result := _check_infra_error(state, telemetry, "tester"):
        return result

    if state.get("test_output") == "PASS":
        telemetry.log_status("tester", "success")
        return "architect"

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("tester", "error")
        telemetry.log_workflow_status("failed")
        return END

    telemetry.log_status("tester", "failed")
    return "coder"


def should_continue_from_architect(state: AgentState) -> str:
    telemetry = get_telemetry()
    if result := _check_infra_error(state, telemetry, "architect"):
        return result

    status = state.get("architect_status")

    if status == "ok":
        telemetry.log_status("architect", "success")
        return "reviewer"

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("architect", "error")
        telemetry.log_workflow_status("failed")
        return END

    telemetry.log_status("architect", status if status else "error")
    if status == "error":
        return "architect"

    return "coder"


def should_continue_from_review(state: AgentState) -> str:
    telemetry = get_telemetry()
    if result := _check_infra_error(state, telemetry, "reviewer"):
        return result

    status = state.get("review_status")

    if status == "approved":
        telemetry.log_status("reviewer", "success")
        return "pr_pre_checker"

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("reviewer", "error")
        telemetry.log_workflow_status("failed")
        return END

    telemetry.log_status("reviewer", status if status else "error")
    if status == "error":
        return "reviewer"

    if status == "pr_failed":
        return "pr_failed"

    return "coder"


def should_continue_from_pr_creator(state: AgentState) -> str:
    telemetry = get_telemetry()
    if result := _check_infra_error(state, telemetry, "pr_creator"):
        return result

    status = state.get("review_status")

    if status == "pr_created":
        telemetry.log_status("pr_creator", "success")
        return END

    if status == "pr_skipped":
        telemetry.log_status("pr_creator", "success")
        return END

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded in PR Creator. Aborting.")
        telemetry.log_status("pr_creator", "error")
        telemetry.log_workflow_status("failed")
        return END

    print(
        f"PR Creator failed or needs commit (status: {repr(status)}). Returning to coder."
    )
    telemetry.log_status("pr_creator", "failed")
    return "coder"


def should_continue_from_pr_pre_checker(state: AgentState) -> str:
    telemetry = get_telemetry()
    if result := _check_infra_error(state, telemetry, "pr_pre_checker"):
        return result

    status = state.get("review_status")

    if status == "pre_check_passed":
        telemetry.log_status("pr_pre_checker", "success")
        return "pr_creator"

    if status == "pr_skipped":
        telemetry.log_status("pr_pre_checker", "success")
        return END

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded in PR Pre-Checker. Aborting.")
        telemetry.log_status("pr_pre_checker", "error")
        telemetry.log_workflow_status("failed")
        return END

    print(
        f"PR Pre-Checker failed or needs commit (status: {repr(status)}). Returning to coder."
    )
    telemetry.log_status("pr_pre_checker", "failed")
    return "coder"


def should_continue_from_journaler(state: AgentState) -> str:
    telemetry = get_telemetry()
    if result := _check_infra_error(state, telemetry, "journaler"):
        return result

    telemetry.log_status("journaler", "success")
    status = state.get("review_status")

    if status == "pre_check_passed":
        return "pr_creator"
    return END


def should_continue_from_coder(state: AgentState) -> str:
    telemetry = get_telemetry()
    if result := _check_infra_error(state, telemetry, "coder"):
        return result

    telemetry.log_status("coder", "success")
    status = state.get("code_status")

    if status == "coded":
        return "tester"

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded from coder. Aborting.")
        telemetry.log_status("coder", "error")
        telemetry.log_workflow_status("failed")
        return END

    print(f"Coder failed (status: {repr(status)}). Retrying...")
    return "coder"
