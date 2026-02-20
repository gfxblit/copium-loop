import re

from langchain_core.messages import SystemMessage

from copium_loop.git import (
    add,
    commit,
    is_dirty,
    push,
)
from copium_loop.nodes.utils import node_header, validate_git_context
from copium_loop.shell import run_command
from copium_loop.state import AgentState
from copium_loop.telemetry import get_telemetry


@node_header("pr_creator")
async def pr_creator_node(state: AgentState) -> dict:
    telemetry = get_telemetry()
    # telemetry.log_status("pr_creator", "active") - removed for decorator

    retry_count = state.get("retry_count", 0)
    issue_url = state.get("issue_url", "")

    try:
        # 1. Validate git context
        branch_name = await validate_git_context("pr_creator")
        if not branch_name:
            return {"review_status": "pr_skipped"}

        # 2. Check uncommitted changes (expected from journaler)
        if await is_dirty(node="pr_creator"):
            msg = "Committing journal updates...\n"
            telemetry.log_info("pr_creator", msg)
            print(msg, end="")
            await add(".", node="pr_creator")
            await commit("docs: update GEMINI.md and session memory", node="pr_creator")

        # 3. Push to origin
        msg = "Pushing to origin...\n"
        telemetry.log_info("pr_creator", msg)
        print(msg, end="")
        res_push = await push(force=True, branch=branch_name, node="pr_creator")
        if res_push["exit_code"] != 0:
            raise Exception(
                f"Git push failed (exit {res_push['exit_code']}): {res_push['output'].strip()}"
            )

        # 4. Create PR
        msg = "Creating Pull Request...\n"
        telemetry.log_info("pr_creator", msg)
        print(msg, end="")
        res_pr = await run_command("gh", ["pr", "create", "--fill"], node="pr_creator")

        if res_pr["exit_code"] != 0:
            if "already exists" in res_pr["output"]:
                msg = "PR already exists. Treating as success.\n"
                telemetry.log_info("pr_creator", msg)
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

        # 5. Link issue if present
        if issue_url:
            msg = f"Linking issue: {issue_url}\n"
            telemetry.log_info("pr_creator", msg)
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
                    telemetry.log_info("pr_creator", msg)
                    print(msg, end="")
            except Exception as e:
                msg = f"Warning: Failed to link issue to PR: {e}\n"
                telemetry.log_info("pr_creator", msg)
                print(msg, end="")

        telemetry.log_status("pr_creator", "success")
        return {
            "review_status": "pr_created",
            "pr_url": pr_output_clean,
            "messages": [SystemMessage(content=f"PR Created: {pr_output_clean}")],
        }

    except Exception as error:
        msg = f"Error in PR creation: {error}\n"
        telemetry.log_info("pr_creator", msg)
        print(msg, end="")
        telemetry.log_status("pr_creator", "failed")
        return {
            "review_status": "pr_failed",
            "messages": [SystemMessage(content=f"Failed to create PR: {error}")],
            "retry_count": retry_count + 1,
        }
