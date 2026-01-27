import os
import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import REVIEWER_MODELS
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry
from copium_loop.utils import invoke_gemini, run_command


async def reviewer(state: AgentState) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("reviewer", "active")
    telemetry.log_output("reviewer", "--- Reviewer Node ---\n")
    print("--- Reviewer Node ---")
    test_output = state.get("test_output", "")
    retry_count = state.get("retry_count", 0)
    initial_commit_hash = state.get("initial_commit_hash", "")

    if test_output and "PASS" not in test_output:
        telemetry.log_status("reviewer", "rejected")
        return {
            "review_status": "rejected",
            "messages": [SystemMessage(content="Tests failed.")],
            "retry_count": retry_count + 1,
        }

    git_diff = ""
    if os.path.exists(".git") and initial_commit_hash:
        try:
            res = await run_command(
                "git", ["diff", initial_commit_hash, "HEAD"], node="reviewer"
            )
            if res["exit_code"] == 0:
                git_diff = res["output"]
        except Exception as e:
            msg = f"Warning: Failed to get git diff: {e}\n"
            telemetry.log_output("reviewer", msg)
            print(msg, end="")

    system_prompt = f"""You are a senior reviewer. Your task is to review the implementation provided by the current branch.

    GIT DIFF SINCE START:
    {git_diff}

    Your primary responsibility is to ensure the code changes do not introduce critical or high-severity issues.

    CRITICAL REQUIREMENTS:
    1. ONLY reject if there are CRITICAL or HIGH severity issues introduced by the changes in the git diff.
    2. Do NOT reject for minor stylistic issues, missing comments, or non-critical best practices.
    3. If the logic is correct and passes tests (which it has if you are seeing this), and no high-severity bugs are obvious in the diff, you SHOULD APPROVE.
    4. Focus ONLY on the changes introduced in the diff.

    To do this, you MUST activate the 'code-reviewer' skill and provide it with the necessary context, including the git diff above.
    Instruct the skill to focus ONLY on identifying critical or high severity issues within the changes.
    After the skill completes its review, you will receive its output. Based solely on the skill's verdict ("APPROVED" or "REJECTED"),
    determine the final status of the review. Do not make any fixes or changes yourself; rely entirely on the 'code-reviewer' skill's output."""

    try:
        review_content = await invoke_gemini(
            system_prompt,
            ["--yolo"],
            models=REVIEWER_MODELS,
            verbose=state.get("verbose"),
            label="Reviewer System",
            node="reviewer",
        )
    except Exception as e:
        msg = f"Error during review: {e}\n"
        telemetry.log_output("reviewer", msg)
        print(msg, end="")
        telemetry.log_status("reviewer", "rejected")
        return {
            "review_status": "rejected",
            "messages": [SystemMessage(content=f"Reviewer encountered an error: {e}")],
            "retry_count": retry_count + 1,
        }

    # Robustly check for the final verdict by looking for the last occurrence of APPROVED or REJECTED
    verdicts = re.findall(r"\b(APPROVED|REJECTED)\b", review_content.upper())
    is_approved = verdicts[-1] == "APPROVED" if verdicts else False

    msg = f"\nReview decision: {'Approved' if is_approved else 'Rejected'}\n"
    telemetry.log_output("reviewer", msg)
    print(msg, end="")
    telemetry.log_status("reviewer", "approved" if is_approved else "rejected")

    return {
        "review_status": "approved" if is_approved else "rejected",
        "messages": [SystemMessage(content=review_content)],
        "retry_count": retry_count if is_approved else retry_count + 1,
    }
