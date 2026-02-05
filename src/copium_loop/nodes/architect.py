import os
import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import MODELS
from copium_loop.gemini import invoke_gemini
from copium_loop.git import get_diff
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


def _parse_verdict(content: str) -> str | None:
    """Parses the architect content for the final verdict (OK or REFACTOR)."""
    # Look for "VERDICT: OK" or "VERDICT: REFACTOR"
    matches = re.findall(r"VERDICT:\s*(OK|REFACTOR)", content.upper())
    if matches:
        return matches[-1]
    return None


async def architect(state: AgentState) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("architect", "active")
    telemetry.log_output("architect", "--- Architect Node ---\n")
    print("--- Architect Node ---")
    retry_count = state.get("retry_count", 0)
    initial_commit_hash = state.get("initial_commit_hash", "")

    git_diff = ""
    if os.path.exists(".git") and initial_commit_hash:
        try:
            git_diff = await get_diff(initial_commit_hash, head=None, node="architect")
        except Exception as e:
            msg = f"Warning: Failed to get git diff: {e}\n"
            telemetry.log_output("architect", msg)
            print(msg, end="")

    system_prompt = f"""You are a software architect. Your task is to evaluate the code changes for architectural integrity.

    GIT DIFF SINCE START:
    {git_diff}

    Your primary responsibility is to ensure the code changes adhere to architectural best practices:
    1. Single Responsibility Principle (SRP): Each module/class should have one reason to change.
    2. Modularity: The code should be well-organized and modular.
    3. Open/Closed Principle (OCP): Entities should be open for extension but closed for modification.
    4. File Size: Ensure files are not becoming too large and unwieldy.

    You MUST provide your final verdict in the format: "VERDICT: OK" or "VERDICT: REFACTOR".

    CRITICAL: You MUST NOT use any tools to modify the filesystem (e.g., 'write_file', 'replace'). You are an evaluator only.

    To do this, you MUST activate the 'architect' skill and provide it with the necessary context, including the git diff above.
    Instruct the skill to evaluate the diff for modularity, SRP, OCP, and overall architecture.
    After the skill completes its evaluation, you will receive its output. Based solely on the skill's verdict ("OK" or "REFACTOR"),
    determine the final status. Do not make any fixes or changes yourself; rely entirely on the 'architect' skill's output."""

    try:
        architect_content = await invoke_gemini(
            system_prompt,
            ["--yolo"],
            models=MODELS,
            verbose=state.get("verbose"),
            label="Architect System",
            node="architect",
        )
    except Exception as e:
        msg = f"Error during architectural evaluation: {e}\n"
        telemetry.log_output("architect", msg)
        print(msg, end="")
        telemetry.log_status("architect", "error")
        return {
            "architect_status": "error",
            "messages": [SystemMessage(content=f"Architect encountered an error: {e}")],
            "retry_count": retry_count + 1,
        }

    verdict = _parse_verdict(architect_content)
    if not verdict:
        msg = "\nArchitectural decision: Error (no verdict found)\n"
        telemetry.log_output("architect", msg)
        print(msg, end="")
        telemetry.log_status("architect", "error")
        return {
            "architect_status": "error",
            "messages": [SystemMessage(content=architect_content)],
            "retry_count": retry_count + 1,
        }

    is_ok = verdict == "OK"
    msg = f"\nArchitectural decision: {'OK' if is_ok else 'REFACTOR'}\n"
    telemetry.log_output("architect", msg)
    print(msg, end="")
    telemetry.log_status("architect", "ok" if is_ok else "refactor")

    return {
        "architect_status": "ok" if is_ok else "refactor",
        "messages": [SystemMessage(content=architect_content)],
        "retry_count": retry_count if is_ok else retry_count + 1,
    }
