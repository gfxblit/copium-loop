import os
import re

from langchain_core.messages import SystemMessage

from copium_loop.constants import MAX_RETRIES
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry
from copium_loop.utils import notify, run_command


async def pr_creator(state: AgentState) -> dict:
    telemetry = get_telemetry()
    telemetry.log_status("pr_creator", "active")
    telemetry.log_output("pr_creator", "--- PR Creator Node ---\n")
    print("--- PR Creator Node ---")
    retry_count = state.get("retry_count", 0)
    issue_url = state.get("issue_url", "")

    if not os.path.exists(".git"):
        msg = "Not a git repository. Skipping PR creation.\n"
        telemetry.log_output("pr_creator", msg)
        print(msg, end="")
        telemetry.log_status("pr_creator", "success")
        return {"review_status": "pr_skipped"}

    try:
        # 1. Check feature branch
        res_branch = await run_command(
            "git", ["branch", "--show-current"], node="pr_creator"
        )
        branch_name = res_branch["output"].strip()

        if (
            res_branch["exit_code"] != 0
            or branch_name in ["main", "master"]
            or not branch_name
        ):
            msg = "Not on a feature branch. Skipping PR creation.\n"
            telemetry.log_output("pr_creator", msg)
            print(msg, end="")
            telemetry.log_status("pr_creator", "success")
            return {"review_status": "pr_skipped"}

        msg = f"On feature branch: {branch_name}\n"
        telemetry.log_output("pr_creator", msg)
        print(msg, end="")

        # 2. Check uncommitted changes
        res_status = await run_command(
            "git", ["status", "--porcelain"], node="pr_creator"
        )
        if res_status["output"].strip():
            msg = "Uncommitted changes found. Returning to coder to finalize commits.\n"
            telemetry.log_output("pr_creator", msg)
            print(msg, end="")
            telemetry.log_status("pr_creator", "failed")
            return {
                "review_status": "needs_commit",
                "messages": [
                    SystemMessage(
                        content="Uncommitted changes found. Please ensure all changes are committed before creating a PR."
                    )
                ],
                "retry_count": retry_count + 1,
            }

        # 3. Attempt rebase on origin/main
        msg = "Fetching origin and attempting rebase on origin/main...\n"
        telemetry.log_output("pr_creator", msg)
        print(msg, end="")
        await run_command("git", ["fetch", "origin"], node="pr_creator")
        res_rebase = await run_command(
            "git", ["rebase", "origin/main"], node="pr_creator"
        )

        if res_rebase["exit_code"] != 0:
            msg = "Rebase failed. Aborting rebase and returning to coder.\n"
            telemetry.log_output("pr_creator", msg)
            print(msg, end="")
            await run_command("git", ["rebase", "--abort"], node="pr_creator")
            error_msg = f"Automatic rebase on origin/main failed with the following error:\n{res_rebase['output']}\n\nThe rebase has been aborted to keep the repository in a clean state. Please manually resolve the conflicts by running 'git rebase origin/main', fixing the files, and committing the changes before trying again."
            await notify(
                "Workflow: Rebase Conflict",
                "Automatic rebase failed. Manual resolution required by coder.",
                4,
            )
            telemetry.log_status("pr_creator", "failed")
            return {
                "review_status": "pr_failed",
                "messages": [SystemMessage(content=error_msg)],
                "retry_count": retry_count + 1,
            }

        # 4. Push to origin
        msg = "Pushing to origin...\n"
        telemetry.log_output("pr_creator", msg)
        print(msg, end="")
        res_push = await run_command(
            "git", ["push", "--force", "-u", "origin", branch_name], node="pr_creator"
        )
        if res_push["exit_code"] != 0:
            raise Exception(
                f"Git push failed (exit {res_push['exit_code']}): {res_push['output'].strip()}"
            )

        # 5. Create PR
        msg = "Creating Pull Request...\n"
        telemetry.log_output("pr_creator", msg)
        print(msg, end="")
        res_pr = await run_command("gh", ["pr", "create", "--fill"], node="pr_creator")

        if res_pr["exit_code"] != 0:
            if "already exists" in res_pr["output"]:
                msg = "PR already exists. Treating as success.\n"
                telemetry.log_output("pr_creator", msg)
                print(msg, end="")
                match = re.search(r"https://github\.com/[^\s]+", res_pr["output"])
                pr_url = match.group(0) if match else "existing PR"
                telemetry.log_status("pr_creator", "success")
                return {
                    "review_status": "pr_created",
                    "pr_url": pr_url,
                    "messages": [SystemMessage(content=f"PR already exists: {pr_url}")],
                }
            raise Exception(
                f"PR creation failed (exit {res_pr['exit_code']}): {res_pr['output'].strip()}"
            )

        pr_output_clean = res_pr["output"].strip()
        msg = f"PR created: {pr_output_clean}\n"
        telemetry.log_output("pr_creator", msg)
        print(msg, end="")

        # 6. Link issue if present
        if issue_url:
            msg = f"Linking issue: {issue_url}\n"
            telemetry.log_output("pr_creator", msg)
            print(msg, end="")
            try:
                # Get current body
                res_view = await run_command(
                    "gh",
                    ["pr", "view", pr_output_clean, "--json", "body", "--jq", ".body"],
                    node="pr_creator",
                )
                if res_view["exit_code"] == 0:
                    current_body = res_view["output"].strip()
                    new_body = f"{current_body}\n\nCloses {issue_url}"
                    await run_command(
                        "gh",
                        ["pr", "edit", pr_output_clean, "--body", new_body],
                        node="pr_creator",
                    )
                    msg = "PR body updated with issue reference.\n"
                    telemetry.log_output("pr_creator", msg)
                    print(msg, end="")
            except Exception as e:
                msg = f"Warning: Failed to link issue to PR: {e}\n"
                telemetry.log_output("pr_creator", msg)
                print(msg, end="")

        telemetry.log_status("pr_creator", "success")
        return {
            "review_status": "pr_created",
            "pr_url": pr_output_clean,
            "messages": [SystemMessage(content=f"PR Created: {pr_output_clean}")],
        }

    except Exception as error:
        msg = f"Error in PR creation: {error}\n"
        telemetry.log_output("pr_creator", msg)
        print(msg, end="")
        message = (
            "Max retries exceeded. Aborting."
            if retry_count >= MAX_RETRIES
            else f"Failed to create PR: {error}"
        )
        await notify("Workflow: PR Failed", message, 5)
        telemetry.log_status("pr_creator", "failed")
        return {
            "review_status": "pr_failed",
            "messages": [SystemMessage(content=f"Failed to create PR: {error}")],
            "retry_count": retry_count + 1,
        }
