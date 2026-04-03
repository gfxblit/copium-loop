import os
import shutil
import sys

from copium_loop.git import get_current_branch, get_repo_name, is_dirty, is_git_repo
from copium_loop.shell import run_command


async def run_alldone():
    """Cleans up copium-loop workspace, logs, and sessions for the current branch."""
    if not await is_git_repo():
        print("Error: Not inside a git repository.")
        sys.exit(1)

    if await is_dirty():
        print("Error: Git repository has uncommitted or untracked files. Aborting.")
        sys.exit(1)

    branch = await get_current_branch()
    repo_name = await get_repo_name()

    # Get toplevel directory
    res = await run_command("git", ["rev-parse", "--show-toplevel"])
    if res["exit_code"] != 0:
        print("Error: Could not determine git repository root.")
        sys.exit(1)

    toplevel_dir = res["output"].strip()

    log_path = os.path.expanduser(f"~/.copium/logs/{repo_name}/{branch}.jsonl")
    session_path = os.path.expanduser(f"~/.copium/sessions/{repo_name}/{branch}.json")

    if os.path.exists(log_path):
        os.remove(log_path)

    if os.path.exists(session_path):
        os.remove(session_path)

    # Kill tmux session
    await run_command(
        "tmux", ["kill-session", "-t", branch], capture_stderr=False, check=False
    )

    # Change directory before removing it
    os.chdir("..")
    shutil.rmtree(toplevel_dir)

    print(
        f"Successfully cleaned up copium-loop workspace for '{branch}' in '{repo_name}'."
    )
