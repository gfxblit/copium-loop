from copium_loop.shell import run_command


async def get_current_branch() -> str:
    """Returns the current git branch name."""
    res = await run_command("git", ["branch", "--show-current"])
    return res["output"].strip()


async def get_diff(base: str, head: str = "HEAD", node: str | None = None) -> str:
    """Returns the git diff between two commits."""
    res = await run_command("git", ["diff", base, head], node=node)
    return res["output"]


async def is_dirty() -> bool:
    """Returns True if the git repository has uncommitted changes."""
    res = await run_command("git", ["status", "--porcelain"])
    return bool(res["output"].strip())


async def get_head() -> str:
    """Returns the current HEAD commit hash."""
    res = await run_command("git", ["rev-parse", "HEAD"])
    return res["output"].strip()


async def fetch(remote: str = "origin") -> dict:
    """Fetches updates from the remote repository."""
    return await run_command("git", ["fetch", remote])


async def rebase(target: str) -> dict:
    """Rebases the current branch onto the target."""
    return await run_command("git", ["rebase", target])


async def rebase_abort() -> dict:
    """Aborts an ongoing rebase."""
    return await run_command("git", ["rebase", "--abort"])


async def push(
    force: bool = False, remote: str = "origin", branch: str | None = None
) -> dict:
    """Pushes the current branch to the remote repository."""
    args = ["push"]
    if force:
        args.append("--force")
    if branch:
        args.extend(["-u", remote, branch])
    else:
        args.append(remote)
    return await run_command("git", args)
