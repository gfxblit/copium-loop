import asyncio
import os
import re

from copium_loop.engine.base import LLMEngine
from copium_loop.shell import run_command, stream_subprocess
from copium_loop.telemetry import get_telemetry


class JulesError(Exception):
    """Base exception for JulesEngine."""


class JulesSessionError(JulesError):
    """Raised when a Jules session fails or cannot be created."""


class JulesTimeoutError(JulesError):
    """Raised when a Jules operation times out."""


class JulesRepoError(JulesError):
    """Raised when the git repository name cannot be detected."""


# Constants for Jules CLI interactions
DEFAULT_COMMAND_TIMEOUT = 3600
POLLING_INTERVAL = 10
OUTPUT_FILE = "JULES_OUTPUT.txt"
MAX_PROMPT_LENGTH = 12000


class JulesEngine(LLMEngine):
    """Concrete implementation of LLMEngine using Jules CLI."""

    async def _get_repo_name(self, node: str | None = None) -> str:
        """Extracts owner/repo from git remotes."""
        # Try origin first, then any available remote
        remotes_to_try = ["origin"]
        res = await run_command("git", ["remote"], node=node, capture_stderr=False)
        all_remotes = res["output"].strip().splitlines()
        for r in all_remotes:
            if r != "origin":
                remotes_to_try.append(r)

        url = None
        for remote in remotes_to_try:
            try:
                res = await run_command(
                    "git",
                    ["remote", "get-url", remote],
                    node=node,
                    capture_stderr=True,
                )
                if res["exit_code"] == 0:
                    url = res["output"].strip()
                    break
            except Exception:
                continue

        if not url:
            raise JulesRepoError("Could not determine git remote URL.")

        # Regex to match github.com/owner/repo or git@github.com:owner/repo
        # Improved to handle trailing slashes and multiple segments (for GitLab etc)
        match = re.search(r"[:/]([^/:]+/[^/:]+?)(?:\.git)?/?$", url)
        if match:
            return match.group(1)

        raise JulesRepoError(f"Could not parse repo name from remote URL: {url}")

    async def invoke(
        self,
        prompt: str,
        _args: list[str] | None = None,
        _models: list[str | None] | None = None,
        verbose: bool = False,
        label: str | None = None,
        node: str | None = None,
        command_timeout: int | None = None,
        inactivity_timeout: int | None = None,
    ) -> str:
        """
        Invokes the Jules CLI to create a remote session, polls for completion,
        and pulls the results.
        """
        if node:
            get_telemetry().log(node, "prompt", prompt)

        if verbose:
            banner = (
                f"--- [VERBOSE] {label} Prompt ---"
                if label
                else "--- [VERBOSE] Prompt ---"
            )
            print(f"\n{banner}")
            print(prompt)
            print("-" * len(banner) + "\n")

        # Cleanup stale output file if it exists
        if os.path.exists(OUTPUT_FILE):
            try:
                os.remove(OUTPUT_FILE)
            except OSError as e:
                print(f"Warning: Could not remove stale {OUTPUT_FILE}: {e}")

        try:
            repo = await self._get_repo_name(node=node)

            # Sanitize prompt to prevent injection
            safe_prompt = self.sanitize_for_prompt(prompt, max_length=MAX_PROMPT_LENGTH)

            # Instruct Jules to write to JULES_OUTPUT.txt
            prompt_with_instr = (
                f"{safe_prompt}\n\n"
                f"IMPORTANT: Write your final summary or verdict to {OUTPUT_FILE} "
                "before finishing."
            )

            # 1. Create session
            # Use a longer timeout for Jules session creation/upload if needed
            timeout = (
                command_timeout
                if command_timeout is not None
                else DEFAULT_COMMAND_TIMEOUT
            )

            env = os.environ.copy()
            # Prevent interactive prompts
            env.update({"GH_PROMPT_DISABLED": "1"})

            output, exit_code, timed_out, timeout_message = await stream_subprocess(
                "jules",
                ["remote", "new", "--repo", repo, "-p", prompt_with_instr],
                env,
                node,
                timeout,
                inactivity_timeout=inactivity_timeout,
                capture_stderr=True,
            )

            if timed_out:
                raise JulesTimeoutError(
                    f"Jules session creation timed out: {timeout_message}"
                )
            if exit_code != 0:
                raise JulesSessionError(
                    f"Jules session creation failed with code {exit_code}: {output}"
                )

            match = re.search(r"Session ID: (\S+)", output)
            if not match:
                raise JulesSessionError(
                    f"Failed to parse Session ID from Jules output: {output}"
                )
            session_id = match.group(1)

            if verbose:
                print(f"Jules session created: {session_id}")

            # 2. Poll for completion
            while True:
                output, exit_code, timed_out, timeout_message = await stream_subprocess(
                    "jules",
                    ["remote", "list", "--session", session_id],
                    env,
                    node,
                    timeout,
                    capture_stderr=True,
                )
                if timed_out:
                    raise JulesTimeoutError(
                        f"Polling Jules session timed out: {timeout_message}"
                    )

                if "Status: Completed" in output:
                    break
                elif "Status: Failed" in output:
                    raise JulesSessionError(f"Jules session {session_id} failed.")

                await asyncio.sleep(POLLING_INTERVAL)

            # 3. Pull results
            output, exit_code, timed_out, timeout_message = await stream_subprocess(
                "jules",
                ["remote", "pull", "--session", session_id, "--apply"],
                env,
                node,
                timeout,
                capture_stderr=True,
            )
            if timed_out:
                raise JulesTimeoutError(
                    f"Pulling Jules results timed out: {timeout_message}"
                )
            if exit_code != 0:
                raise JulesSessionError(f"Failed to pull Jules results: {output}")

            # 4. Read JULES_OUTPUT.txt
            try:
                with open(OUTPUT_FILE) as f:
                    return f.read()
            except FileNotFoundError:
                return f"Jules task completed, but {OUTPUT_FILE} was not found."

        finally:
            # Cleanup output file after reading
            if os.path.exists(OUTPUT_FILE):
                try:
                    os.remove(OUTPUT_FILE)
                except OSError as e:
                    print(f"Warning: Could not remove {OUTPUT_FILE} after run: {e}")
