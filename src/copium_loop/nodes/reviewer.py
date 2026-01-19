import os
import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import REVIEWER_MODELS
from copium_loop.state import AgentState
from copium_loop.utils import invoke_gemini, notify, run_command


async def reviewer(state: AgentState) -> dict:
    print("--- Reviewer Node ---")
    test_output = state.get("test_output", "")
    retry_count = state.get("retry_count", 0)
    initial_commit_hash = state.get("initial_commit_hash", "")

    if test_output and "PASS" not in test_output:
        return {
            "review_status": "rejected",
            "messages": [SystemMessage(content="Tests failed.")],
            "retry_count": retry_count + 1,
        }

    git_diff = ""
    if os.path.exists(".git") and initial_commit_hash:
        try:
            res = await run_command("git", ["diff", initial_commit_hash, "HEAD"])
            if res["exit_code"] == 0:
                git_diff = res["output"]
        except Exception as e:
            print(f"Warning: Failed to get git diff: {e}")

    system_prompt = f"""You are a senior reviewer. Your task is to review the implementation provided by the current branch.

    GIT DIFF SINCE START:
    {git_diff}

    Your primary responsibility is to ensure the code changes are correct, idiomatic, and well-tested.

    CRITICAL REQUIREMENTS:
    1. Verify that new tests have been added for any new functionality.
    2. Verify that existing tests have been updated if behavior changed.
    3. If the change is a pure refactor, determine if existing tests provide sufficient coverage.
    4. Reject the implementation if it lacks relevant new tests for new features.
    5. Ensure no debug statements or commented-out code are left behind.

    To do this, you MUST activate the 'code-reviewer' skill and provide it with the necessary context, including the git diff above.
    After the skill completes its review, you will receive its output. Based solely on the skill's verdict ("APPROVED" or "REJECTED"),
    determine the final status of the review. Do not make any fixes or changes yourself; rely entirely on the 'code-reviewer' skill's output."""
    if state.get("verbose"):
        print("\n--- [VERBOSE] Reviewer System Prompt ---")
        print(system_prompt)
        print("--------------------------------------\n")

    review_content = await invoke_gemini(
        system_prompt, ["--yolo"], models=REVIEWER_MODELS, verbose=state.get("verbose")
    )

    # Robustly check for the final verdict by looking for the last occurrence of APPROVED or REJECTED
    verdicts = re.findall(r"\b(APPROVED|REJECTED)\b", review_content.upper())
    is_approved = verdicts[-1] == "APPROVED" if verdicts else False

    print(f"\nReview decision: {'Approved' if is_approved else 'Rejected'}")

    if not is_approved:
        message = (
            "Max retries exceeded. Aborting."
            if retry_count >= 3
            else "Reviewer rejected the implementation. Returning to coder."
        )
        await notify("Workflow: Review Rejected", message, 4)

    return {
        "review_status": "approved" if is_approved else "rejected",
        "messages": [SystemMessage(content=review_content)],
        "retry_count": retry_count if is_approved else retry_count + 1,
    }
