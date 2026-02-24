from langchain_core.messages import SystemMessage

from copium_loop.git import (
    fetch,
    is_dirty,
    rebase,
    rebase_abort,
)
from copium_loop.nodes.utils import node_header, validate_git_context
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


@node_header("pr_pre_checker")
async def pr_pre_checker_node(state: AgentState) -> dict:
    telemetry = get_telemetry()
    # telemetry.log_status("pr_pre_checker", "active") - decorator handles this

    retry_count = state.get("retry_count", 0)

    try:
        # 1. Validate git context
        if not await validate_git_context("pr_pre_checker"):
            return {"review_status": "pr_skipped"}

        # 2. Check uncommitted changes
        if await is_dirty(node="pr_pre_checker"):
            msg = "Uncommitted changes found. Returning to coder.\n"
            telemetry.log_info("pr_pre_checker", msg)
            print(msg, end="")
            telemetry.log_status("pr_pre_checker", "failed")
            error_msg = "Uncommitted changes found. Please ensure all changes are committed before creating a PR."
            return {
                "review_status": "needs_commit",
                "messages": [SystemMessage(content=error_msg)],
                "retry_count": retry_count + 1,
                "last_error": error_msg,
            }

        # 3. Attempt rebase on origin/main
        msg = "Syncing with origin/main...\n"
        telemetry.log_info("pr_pre_checker", msg)
        print(msg, end="")
        await fetch(node="pr_pre_checker")
        res_rebase = await rebase("origin/main", node="pr_pre_checker")

        if res_rebase["exit_code"] != 0:
            msg = "Rebase failed. Aborting rebase and returning to coder.\n"
            telemetry.log_info("pr_pre_checker", msg)
            print(msg, end="")
            await rebase_abort(node="pr_pre_checker")
            error_msg = f"Automatic rebase on origin/main failed with the following error:\n{res_rebase['output']}\n\nThe rebase has been aborted to keep the repository in a clean state. Please manually resolve the conflicts by running 'git rebase origin/main', fixing the files, and committing the changes before trying again."
            telemetry.log_status("pr_pre_checker", "failed")
            return {
                "review_status": "pr_failed",
                "messages": [SystemMessage(content=error_msg)],
                "retry_count": retry_count + 1,
                "last_error": error_msg,
            }

        telemetry.log_status("pr_pre_checker", "success")
        return {"review_status": "pre_check_passed"}

    except Exception as error:
        msg = f"Error in PR Pre-Check: {error}\n"
        telemetry.log_info("pr_pre_checker", msg)
        print(msg, end="")
        telemetry.log_status("pr_pre_checker", "failed")
        error_msg = f"PR Pre-Check failed: {error}"
        return {
            "review_status": "pr_failed",
            "messages": [SystemMessage(content=error_msg)],
            "retry_count": retry_count + 1,
            "last_error": error_msg,
        }
