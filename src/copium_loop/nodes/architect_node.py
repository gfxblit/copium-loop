import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import MODELS
from copium_loop.nodes.utils import get_architect_prompt, node_header
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


def _parse_verdict(content: str) -> str | None:
    """Parses the architect content for the final verdict (APPROVED or REJECTED)."""
    # Look for "VERDICT: APPROVED" or "VERDICT: REJECTED"
    matches = re.findall(r"VERDICT:\s*(APPROVED|REJECTED)", content.upper())
    if matches:
        return matches[-1]
    return None


@node_header("architect", status_key="architect_status", error_value="error")
async def architect_node(state: AgentState) -> dict:
    telemetry = get_telemetry()
    # telemetry.log_status("architect", "active") - handled by decorator

    engine = state["engine"]
    retry_count = state.get("retry_count", 0)

    system_prompt = await get_architect_prompt(engine.engine_type, state, engine)

    # Check for empty diff (Gemini provides diff in prompt, Jules calculates its own)
    if re.search(r"<git_diff>\s*</git_diff>", system_prompt, re.DOTALL):
        msg = "\nArchitectural decision: APPROVED (no changes to review)\n"
        telemetry.log_info("architect", msg)
        print(msg, end="")
        telemetry.log_status("architect", "approved")
        return {
            "architect_status": "approved",
            "messages": [
                SystemMessage(
                    content="No changes detected. Skipping architectural review."
                )
            ],
            "retry_count": retry_count,
        }

    architect_content = await engine.invoke(
        system_prompt,
        ["--yolo"],
        models=MODELS,
        verbose=state.get("verbose"),
        label="Architect System",
        node="architect",
    )

    verdict = _parse_verdict(architect_content)
    if not verdict:
        msg = "\nArchitectural decision: Error (no verdict found)\n"
        telemetry.log_info("architect", msg)
        print(msg, end="")
        telemetry.log_status("architect", "error")
        return {
            "architect_status": "error",
            "messages": [SystemMessage(content=architect_content)],
            "retry_count": retry_count + 1,
            "last_error": architect_content,
        }

    is_approved = verdict == "APPROVED"
    msg = f"\nArchitectural decision: {'APPROVED' if is_approved else 'REJECTED'}\n"
    telemetry.log_info("architect", msg)
    print(msg, end="")
    telemetry.log_status("architect", "approved" if is_approved else "rejected")

    return {
        "architect_status": "approved" if is_approved else "rejected",
        "messages": [SystemMessage(content=architect_content)],
        "retry_count": retry_count if is_approved else retry_count + 1,
        "last_error": "" if is_approved else architect_content,
    }
