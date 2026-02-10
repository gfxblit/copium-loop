from copium_loop.shell import run_command


async def is_git_repo(node: str | None = None) -> bool:
    """Returns True if the current directory is inside a git repository."""
    res = await run_command("git", ["rev-parse", "--is-inside-work-tree"], node=node)
    return res["exit_code"] == 0


async def get_current_branch(node: str | None = None) -> str:
    """Returns the current git branch name."""
    res = await run_command("git", ["branch", "--show-current"], node=node)
    return res["output"].strip()


async def get_diff(
    base: str, head: str | None = "HEAD", node: str | None = None
) -> str:
    """Returns the git diff between two commits."""
    args = ["diff", base]
    if head:
        args.append(head)
    res = await run_command("git", args, node=node)
    return res["output"]


async def is_dirty(node: str | None = None) -> bool:
    """Returns True if the git repository has uncommitted changes."""
    res = await run_command("git", ["status", "--porcelain"], node=node)
    return bool(res["output"].strip())


async def get_head(node: str | None = None) -> str:
    """Returns the current HEAD commit hash."""
    res = await run_command("git", ["rev-parse", "HEAD"], node=node)
    return res["output"].strip()


async def resolve_ref(ref: str, node: str | None = None) -> str | None:
    """Resolves a git ref to a commit hash. Returns None if ref doesn't exist."""
    res = await run_command("git", ["rev-parse", "--verify", ref], node=node)
    if res["exit_code"] == 0:
        return res["output"].strip()
    return None


async def fetch(remote: str = "origin", node: str | None = None) -> dict:
    """Fetches updates from the remote repository."""
    return await run_command("git", ["fetch", remote], node=node)


async def rebase(target: str, node: str | None = None) -> dict:
    """Rebases the current branch onto the target."""
    return await run_command("git", ["rebase", target], node=node)


async def rebase_abort(node: str | None = None) -> dict:
    """Aborts an ongoing rebase."""
    return await run_command("git", ["rebase", "--abort"], node=node)


async def push(
    force: bool = False,
    remote: str = "origin",
    branch: str | None = None,
    node: str | None = None,
) -> dict:
    """Pushes the current branch to the remote repository."""
    args = ["push"]
    if force:
        args.append("--force")
    if branch:
        args.extend(["-u", remote, branch])
    else:
        args.append(remote)
    return await run_command("git", args, node=node)


async def add(path: str = ".", node: str | None = None) -> dict:
    """Adds files to the staging area."""
    return await run_command("git", ["add", path], node=node)


async def commit(message: str, node: str | None = None) -> dict:
    """Commits staged changes."""
    return await run_command("git", ["commit", "-m", message], node=node)
