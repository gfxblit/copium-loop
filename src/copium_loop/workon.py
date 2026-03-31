import asyncio
import json
import os
import re
import shlex
import shutil
import sys

from copium_loop.shell import run_command
from copium_loop.tmux import TmuxManager


def slugify(text: str) -> str:
    """Slugify text for branch names."""
    # Convert to lowercase
    text = text.lower()
    # Replace non-alphanumeric with hyphen
    text = re.sub(r"[^a-z0-9]+", "-", text)
    # Remove leading/trailing hyphens
    text = text.strip("-")
    return text


async def find_remote_url(issue_input: str | None = None) -> str | None:
    """Find the remote URL from issue input, .workon-remote or sibling directories."""
    # 1. Check if issue_input is a GitHub URL or SSH URL
    if issue_input:
        if issue_input.startswith("git@github.com:"):
            return issue_input

        if issue_input.startswith("https://github.com/") or issue_input.startswith(
            "http://github.com/"
        ):
            # Extract owner/repo from URL
            # e.g. https://github.com/gfxblit/copium-loop/issues/300
            # or https://github.com/gfxblit/copium-loop
            # or https://github.com/gfxblit/some.repo
            parts = issue_input.split("/")
            if len(parts) >= 5:
                owner = parts[3]
                repo = parts[4]
                # repo might be followed by /issues/300 or .git
                # If it's just the repo name, it might have .git suffix already
                # or it might have dots in the name.
                # We want to strip /issues/... or other subpaths if they exist.
                # parts[4] could be 'some.repo' or 'some.repo.git' or 'copium-loop'
                repo = repo.removesuffix(".git")
                return f"https://github.com/{owner}/{repo}.git"
            elif len(parts) == 4:
                # e.g. https://github.com/gfxblit/copium-loop
                owner = parts[3]
                # This case is less likely for issue_input but possible if repo URL provided
                # Wait, if parts is ["https:", "", "github.com", "owner", "repo"] len is 5.
                # If it's ["https:", "", "github.com", "owner"] len is 4.
                pass

    cwd = os.getcwd()

    # 2. Check for .workon-remote
    dotfile = os.path.join(cwd, ".workon-remote")
    if os.path.exists(dotfile):
        with open(dotfile) as f:
            return f.read().strip()

    # 3. Check sibling directories for git remotes
    for item in os.listdir(cwd):
        path = os.path.join(cwd, item)
        if os.path.isdir(path) and os.path.exists(os.path.join(path, ".git")):
            # Try to get remote URL from this directory
            res = await run_command(
                "git", ["remote", "get-url", "origin"], dir_path=path
            )
            if res["exit_code"] == 0:
                url = res["output"].strip()
                if url:
                    return url

    return None


async def resolve_branch_name(input_str: str) -> str:
    """Resolve a branch name from a URL or description."""
    if input_str.startswith("http://") or input_str.startswith("https://"):
        # Fetch issue info using gh
        res = await run_command(
            "gh", ["issue", "view", "--", input_str, "--json", "title,number"]
        )
        if res["exit_code"] == 0:
            try:
                # Some versions of gh might return different formats if --json is not supported or used differently
                # Let's try to handle both json and text if needed
                # The test mocked it as title:\t...\nnumber:\t...
                # Actually, --json is more robust.
                data = json.loads(res["output"])
                title = data.get("title", "")
                number = data.get("number", "")
                return f"{slugify(title)}-issue{number}"
            except json.JSONDecodeError:
                # Fallback to parsing text if json fails
                output = res["output"]
                title = ""
                number = ""
                for line in output.splitlines():
                    if line.startswith("title:\t"):
                        title = line.replace("title:\t", "").strip()
                    elif line.startswith("number:\t"):
                        number = line.replace("number:\t", "").strip()
                if title and number:
                    return f"{slugify(title)}-issue{number}"

        # Fallback if gh fails
        return slugify(input_str)

    return slugify(input_str)


async def check_dependencies():
    """Check if required external tools are installed."""
    tools = ["gh", "tmux", "git", "pnpm"]
    missing = [tool for tool in tools if not shutil.which(tool)]

    if missing:
        print(f"Error: Missing required tools: {', '.join(missing)}")
        if "gh" in missing:
            print("Please install GitHub CLI: https://cli.github.com/")
        if "tmux" in missing:
            print("Please install tmux: https://github.com/tmux/tmux")
        if "pnpm" in missing:
            print("Please install pnpm: https://pnpm.io/")
        sys.exit(1)


async def workon_main(args):
    """Main function for 'workon' subcommand."""
    await check_dependencies()

    # 1. Resolve branch name

    issue_input = args.issue
    branch_name = await resolve_branch_name(issue_input)
    print(f"Resolved branch name: {branch_name}")

    # 2. Find remote URL
    remote_url = await find_remote_url(issue_input)
    if not remote_url:
        print(
            "Error: Could not find remote URL. Create a .workon-remote file or run from a directory with sibling git repositories."
        )
        sys.exit(1)

    cwd = os.getcwd()
    workspace_path = os.path.join(cwd, branch_name)

    # 3. Create workspace directory and clone (if not exists)
    if not os.path.exists(workspace_path):
        print(f"Cloning {remote_url} into {workspace_path}...")
        res = await run_command(
            "git", ["clone", "-b", branch_name, "--", remote_url, branch_name]
        )
        if res["exit_code"] != 0:
            # Maybe the branch doesn't exist yet, try cloning default and creating branch
            print(
                f"Branch '{branch_name}' not found on remote. Cloning default branch..."
            )
            res = await run_command("git", ["clone", "--", remote_url, branch_name])
            if res["exit_code"] != 0:
                print(f"Error cloning repository: {res['output']}")
                sys.exit(1)

            # Create branch
            print(f"Creating branch '{branch_name}'...")
            await run_command(
                "git", ["checkout", "-b", branch_name], dir_path=workspace_path
            )
    else:
        print(f"Workspace {workspace_path} already exists.")
        # Ensure we are on the correct branch
        await run_command("git", ["checkout", branch_name], dir_path=workspace_path)

    # 4. Detect and run pnpm install
    if os.path.exists(os.path.join(workspace_path, "pnpm-lock.yaml")):
        print("pnpm project detected. Running pnpm install...")
        await run_command("pnpm", ["install"], dir_path=workspace_path)

    # 5. Orchestrate tmux session
    tmux = TmuxManager()
    if not tmux.has_session(branch_name):
        print(f"Creating tmux session: {branch_name}")
        tmux.new_session(branch_name, workspace_path)

        # Bootstrap the AI agent
        bootstrap_prompt = f"I am working on issue {issue_input}. Please analyze the requirements and create a plan."
        bootstrap_cmd = f"copium-loop {shlex.quote(bootstrap_prompt)}"

        # Wait a moment for tmux to settle?
        await asyncio.sleep(0.5)

        tmux.send_keys(branch_name, [bootstrap_cmd, "Enter"])
    else:
        print(f"Tmux session {branch_name} already exists.")

    # 6. Attach or switch to the session
    if os.environ.get("TMUX"):
        print(f"Switching to tmux session: {branch_name}")
        tmux.switch_client(branch_name)
    else:
        print(f"Attaching to tmux session: {branch_name}")
        tmux.attach_session(branch_name)
