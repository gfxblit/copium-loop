import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import MODELS
from copium_loop.nodes.utils import get_reviewer_prompt
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


def _parse_verdict(content: str) -> str | None:
    """Parses the review content for the final verdict (APPROVED or REJECTED)."""
    # Look for "VERDICT: APPROVED" or "VERDICT: REJECTED"
    matches = re.findall(r"VERDICT:\s*(APPROVED|REJECTED)", content.upper())
    if matches:
        return matches[-1]
    return None


async def reviewer_node(state: AgentState) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("reviewer", "active")
    telemetry.log_info("reviewer", "--- Reviewer Node ---\n")
    print("--- Reviewer Node ---")
    engine = state["engine"]
    test_output = state.get("test_output", "")
    retry_count = state.get("retry_count", 0)

    if test_output and "PASS" not in test_output:
        telemetry.log_status("reviewer", "rejected")
        return {
            "review_status": "rejected",
            "messages": [SystemMessage(content="Tests failed.")],
            "retry_count": retry_count + 1,
        }

    try:
        system_prompt = await get_reviewer_prompt(engine.engine_type, state, engine)
    except Exception as e:
        msg = f"Error generating reviewer prompt: {e}\n"
        telemetry.log_info("reviewer", msg)
        print(msg, end="")
        telemetry.log_status("reviewer", "error")
        return {
            "review_status": "error",
            "messages": [SystemMessage(content=f"Reviewer encountered an error: {e}")],
            "retry_count": retry_count + 1,
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
        return {
            "review_status": "error",
            "messages": [SystemMessage(content=f"Reviewer encountered an error: {e}")],
            "retry_count": retry_count + 1,
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
        }

    is_approved = verdict == "APPROVED"
    msg = f"\nReview decision: {'Approved' if is_approved else 'Rejected'}\n"
    telemetry.log_info("reviewer", msg)
    print(msg, end="")
    telemetry.log_status("reviewer", "approved" if is_approved else "rejected")

    return {
        "review_status": "approved" if is_approved else "rejected",
        "messages": [SystemMessage(content=review_content)],
        "retry_count": retry_count if is_approved else retry_count + 1,
    }
