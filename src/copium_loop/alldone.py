import shutil
from pathlib import Path

from copium_loop.git import get_current_branch, get_repo_name, is_dirty, is_git_repo
from copium_loop.shell import run_command


class AllDoneCommand:
    def __init__(self, log_dir: Path, session_dir: Path):
        self.log_dir = log_dir
        self.session_dir = session_dir

    async def execute(self) -> int:
        if not await is_git_repo():
            print("Error: Not inside a git repository.")
            return 1

        if await is_dirty():
            print("Error: Git repository has uncommitted or untracked files. Aborting.")
            return 1

        branch = await get_current_branch()
        repo_name = await get_repo_name()

        # Get toplevel directory
        res = await run_command("git", ["rev-parse", "--show-toplevel"])
        if res["exit_code"] != 0:
            print("Error: Could not determine git repository root.")
            return 1

        toplevel_dir = res["output"].strip()

        log_path = self.log_dir / repo_name / f"{branch}.jsonl"
        session_path = self.session_dir / repo_name / f"{branch}.json"

        if log_path.exists():
            log_path.unlink()

        if session_path.exists():
            session_path.unlink()

        # Kill tmux session
        await run_command(
            "tmux", ["kill-session", "-t", branch], capture_stderr=False, check=False
        )

        # Remove the repository folder without changing directory globally
        shutil.rmtree(toplevel_dir)

        print(
            f"Successfully cleaned up copium-loop workspace for '{branch}' in '{repo_name}'."
        )
        return 0


async def run_alldone() -> int:
    """Cleans up copium-loop workspace, logs, and sessions for the current branch."""
    log_dir = Path.home() / ".copium" / "logs"
    session_dir = Path.home() / ".copium" / "sessions"
    command = AllDoneCommand(log_dir, session_dir)
    return await command.execute()
