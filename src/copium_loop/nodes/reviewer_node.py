import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import MODELS
from copium_loop.nodes.utils import get_reviewer_prompt, node_header
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


def _parse_verdict(content: str) -> str | None:
    """Parses the review content for the final verdict (APPROVED, REJECTED, or REFACTOR)."""
    # Look for "VERDICT: APPROVED", "VERDICT: REJECTED", or "VERDICT: REFACTOR"
    matches = re.findall(r"VERDICT:\s*(APPROVED|REJECTED|REFACTOR)", content.upper())
    if matches:
        return matches[-1]

    # Fallback for implicit approval
    content_upper = content.upper()
    implicit_signals = [
        "READY FOR SUBMISSION",
        "ALL PLAN STEPS COMPLETED",
    ]
    if any(signal in content_upper for signal in implicit_signals):
        return "APPROVED"

    return None


@node_header("reviewer")
async def reviewer_node(state: AgentState) -> dict:
    telemetry = get_telemetry()
    # telemetry.log_status("reviewer", "active") - handled by decorator

    engine = state["engine"]
    test_output = state.get("test_output", "")
    retry_count = state.get("retry_count", 0)

    if test_output and "PASS" not in test_output:
        telemetry.log_status("reviewer", "rejected")
        error_msg = "Tests failed."
        return {
            "review_status": "rejected",
            "messages": [SystemMessage(content=error_msg)],
            "retry_count": retry_count + 1,
            "last_error": error_msg,
        }

    try:
        system_prompt = await get_reviewer_prompt(engine.engine_type, state)
    except Exception as e:
        msg = f"Error generating reviewer prompt: {e}\n"
        telemetry.log_info("reviewer", msg)
        print(msg, end="")
        telemetry.log_status("reviewer", "error")
        error_msg = f"Reviewer encountered an error: {e}"
        return {
            "review_status": "error",
            "messages": [SystemMessage(content=error_msg)],
            "retry_count": retry_count + 1,
            "last_error": error_msg,
        }

    # Check for empty diff
    if re.search(r"<git_diff>\s*</git_diff>", system_prompt, re.DOTALL):
        msg = "\nReview decision: Approved (no changes to review)\n"
        telemetry.log_info("reviewer", msg)
        print(msg, end="")
        telemetry.log_status("reviewer", "approved")
        return {
            "review_status": "approved",
            "messages": [
                SystemMessage(content="No changes detected. Skipping review.")
            ],
            "retry_count": retry_count,
        }

    try:
        review_content = await engine.invoke(
            system_prompt,
            ["--yolo"],
            models=MODELS,
            verbose=state.get("verbose"),
            label="Reviewer System",
            node="reviewer",
        )
    except Exception as e:
        msg = f"Error during review: {e}\n"
        telemetry.log_info("reviewer", msg)
        print(msg, end="")
        telemetry.log_status("reviewer", "error")
        error_msg = f"Reviewer encountered an error: {e}"
        return {
            "review_status": "error",
            "messages": [SystemMessage(content=error_msg)],
            "retry_count": retry_count + 1,
            "last_error": error_msg,
        }

    verdict = _parse_verdict(review_content)

    if not verdict:
        msg = "\nReview decision: Error (no verdict found)\n"
        telemetry.log_info("reviewer", msg)
        print(msg, end="")
        telemetry.log_status("reviewer", "error")
        return {
            "review_status": "error",
            "messages": [SystemMessage(content=review_content)],
            "retry_count": retry_count + 1,
            "last_error": review_content,
        }

    is_approved = verdict == "APPROVED"
    is_refactor = verdict == "REFACTOR"

    if is_approved:
        decision = "Approved"
        status = "approved"
    elif is_refactor:
        decision = "Refactor"
        status = "refactor"
    else:
        decision = "Rejected"
        status = "rejected"

    msg = f"\nReview decision: {decision}\n"
    telemetry.log_info("reviewer", msg)
    print(msg, end="")
    telemetry.log_status("reviewer", status)

    return {
        "review_status": status,
        "messages": [SystemMessage(content=review_content)],
        "retry_count": retry_count if is_approved else retry_count + 1,
        "last_error": "" if is_approved else review_content,
    }
