from langgraph.graph import END

from copium_loop import constants
from copium_loop.nodes.utils import is_infrastructure_error
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


def _handle_infra_error(telemetry, node: str, last_error: str) -> str:
    """Helper to handle infrastructure error termination."""
    print(f"\nInfrastructure failure detected in {node}: {last_error}")
    print("Terminating workflow to prevent futile retries.")
    telemetry.log_status(node, "failed")
    telemetry.log_workflow_status("failed")
    return END


def should_continue_from_test(state: AgentState) -> str:
    telemetry = get_telemetry()
    telemetry.log_status("tester", "success")

    last_error = state.get("last_error")
    if last_error and is_infrastructure_error(last_error):
        return _handle_infra_error(telemetry, "tester", last_error)

    if state.get("test_output") == "PASS":
        return "architect"

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("tester", "error")
        telemetry.log_workflow_status("failed")
        return END

    return "coder"


def should_continue_from_architect(state: AgentState) -> str:
    telemetry = get_telemetry()
    status = state.get("architect_status")

    last_error = state.get("last_error")
    if last_error and is_infrastructure_error(last_error):
        return _handle_infra_error(telemetry, "architect", last_error)

    if status == "ok":
        telemetry.log_status("architect", "success")
        return "reviewer"

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("architect", "error")
        telemetry.log_workflow_status("failed")
        return END

    telemetry.log_status("architect", "success")
    if status == "error":
        return "architect"

    return "coder"


def should_continue_from_review(state: AgentState) -> str:
    telemetry = get_telemetry()
    status = state.get("review_status")

    last_error = state.get("last_error")
    if last_error and is_infrastructure_error(last_error):
        return _handle_infra_error(telemetry, "reviewer", last_error)

    if status == "approved":
        telemetry.log_status("reviewer", "success")
        return "pr_pre_checker"

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded. Aborting.")
        telemetry.log_status("reviewer", "error")
        telemetry.log_workflow_status("failed")
        return END

    telemetry.log_status("reviewer", "success")
    if status == "error":
        return "reviewer"

    if status == "pr_failed":
        return "pr_failed"

    return "coder"


def should_continue_from_pr_creator(state: AgentState) -> str:
    telemetry = get_telemetry()
    telemetry.log_status("pr_creator", "success")
    status = state.get("review_status")

    last_error = state.get("last_error")
    if last_error and is_infrastructure_error(last_error):
        return _handle_infra_error(telemetry, "pr_creator", last_error)

    if status == "pr_created":
        return END

    if status == "pr_skipped":
        return END

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded in PR Creator. Aborting.")
        telemetry.log_status("pr_creator", "error")
        telemetry.log_workflow_status("failed")
        return END

    print(
        f"PR Creator failed or needs commit (status: {repr(status)}). Returning to coder."
    )
    return "coder"


def should_continue_from_pr_pre_checker(state: AgentState) -> str:
    telemetry = get_telemetry()
    telemetry.log_status("pr_pre_checker", "success")
    status = state.get("review_status")

    last_error = state.get("last_error")
    if last_error and is_infrastructure_error(last_error):
        return _handle_infra_error(telemetry, "pr_pre_checker", last_error)

    if status == "pre_check_passed":
        return "pr_creator"

    if status == "pr_skipped":
        return END

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded in PR Pre-Checker. Aborting.")
        telemetry.log_status("pr_pre_checker", "error")
        telemetry.log_workflow_status("failed")
        return END

    print(
        f"PR Pre-Checker failed or needs commit (status: {repr(status)}). Returning to coder."
    )
    return "coder"


def should_continue_from_journaler(state: AgentState) -> str:
    telemetry = get_telemetry()
    telemetry.log_status("journaler", "success")
    status = state.get("review_status")

    last_error = state.get("last_error")
    if last_error and is_infrastructure_error(last_error):
        return _handle_infra_error(telemetry, "journaler", last_error)

    if status == "pre_check_passed":
        return "pr_creator"
    return END


def should_continue_from_coder(state: AgentState) -> str:
    telemetry = get_telemetry()
    telemetry.log_status("coder", "success")
    status = state.get("code_status")

    last_error = state.get("last_error")
    if last_error and is_infrastructure_error(last_error):
        return _handle_infra_error(telemetry, "coder", last_error)

    if status == "coded":
        return "tester"

    if state.get("retry_count", 0) >= constants.MAX_RETRIES:
        print("Max retries exceeded from coder. Aborting.")
        telemetry.log_status("coder", "error")
        telemetry.log_workflow_status("failed")
        return END

    print(f"Coder failed (status: {repr(status)}). Retrying...")
    return "coder"
