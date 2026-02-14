from copium_loop.git import get_current_branch, is_git_repo
from copium_loop.telemetry import get_telemetry


async def validate_git_context(node: str) -> str | None:
    """
    Validates that the current directory is a git repository and that
    we are on a feature branch (not main/master).

    Returns:
        The name of the current branch if validation succeeds.
        None if validation fails.
    """
    telemetry = get_telemetry()

    if not await is_git_repo(node=node):
        msg = "Not a git repository. Skipping PR creation.\n"
        telemetry.log_output(node, msg)
        print(msg, end="")
        telemetry.log_status(node, "success")
        return None

    # Check feature branch
    branch_name = await get_current_branch(node=node)

    if branch_name in ["main", "master", ""]:
        msg = "Not on a feature branch. Skipping PR creation.\n"
        telemetry.log_output(node, msg)
        print(msg, end="")
        telemetry.log_status(node, "success")
        return None

    msg = f"On feature branch: {branch_name}\n"
    telemetry.log_output(node, msg)
    print(msg, end="")

    return branch_name
