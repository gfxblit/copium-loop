import asyncio
import os
import re

from copium_loop.engine.base import LLMEngine
from copium_loop.shell import run_command, stream_subprocess
from copium_loop.telemetry import get_telemetry


class JulesEngine(LLMEngine):
    """Concrete implementation of LLMEngine using Jules CLI."""

    async def _get_repo_name(self, node: str | None = None) -> str:
        """Extracts owner/repo from git remotes."""
        res = await run_command(
            "git", ["remote", "get-url", "origin"], node=node, capture_stderr=False
        )
        url = res["output"].strip()
        # Regex to match github.com/owner/repo or git@github.com:owner/repo
        match = re.search(r"[:/]([^/:]+/[^/:]+)(\.git)?$", url)
        if match:
            return match.group(1).replace(".git", "")
        raise Exception(f"Could not parse repo name from remote URL: {url}")

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

        repo = await self._get_repo_name(node=node)

        # Instruct Jules to write to JULES_OUTPUT.txt
        prompt_with_instr = (
            f"{prompt}\n\n"
            "IMPORTANT: Write your final summary or verdict to JULES_OUTPUT.txt "
            "before finishing."
        )

        # 1. Create session
        # Use a longer timeout for Jules session creation/upload if needed
        timeout = command_timeout if command_timeout is not None else 3600

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
            raise Exception(f"Jules session creation timed out: {timeout_message}")
        if exit_code != 0:
            raise Exception(
                f"Jules session creation failed with code {exit_code}: {output}"
            )

        match = re.search(r"Session ID: (\S+)", output)
        if not match:
            raise Exception(f"Failed to parse Session ID from Jules output: {output}")
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
                raise Exception(f"Polling Jules session timed out: {timeout_message}")

            if "Status: Completed" in output:
                break
            elif "Status: Failed" in output:
                raise Exception(f"Jules session {session_id} failed.")

            await asyncio.sleep(10)

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
            raise Exception(f"Pulling Jules results timed out: {timeout_message}")
        if exit_code != 0:
            raise Exception(f"Failed to pull Jules results: {output}")

        # 4. Read JULES_OUTPUT.txt
        output_path = "JULES_OUTPUT.txt"
        if not os.path.exists(output_path):
            return "Jules task completed, but JULES_OUTPUT.txt was not found."

        with open(output_path) as f:
            return f.read()

    def sanitize_for_prompt(self, text: str, max_length: int = 12000) -> str:
        """
        Sanitizes untrusted text for inclusion in a prompt to prevent injection.
        Escapes common delimiters and truncates excessively long input.
        """
        if not text:
            return ""

        # Escape common XML-like tags to prevent prompt injection breakouts
        replacements = {
            # Closing tags
            "</test_output>": "[/test_output]",
            "</reviewer_feedback>": "[/reviewer_feedback]",
            "</architect_feedback>": "[/architect_feedback]",
            "</git_diff>": "[/git_diff]",
            "</error>": "[/error]",
            "</user_request>": "[/user_request]",
            # Opening tags
            "<test_output>": "[test_output]",
            "<reviewer_feedback>": "[reviewer_feedback]",
            "<architect_feedback>": "[architect_feedback]",
            "<git_diff>": "[git_diff]",
            "<error>": "[error]",
            "<user_request>": "[user_request]",
        }

        safe_text = str(text)
        for tag, replacement in replacements.items():
            safe_text = safe_text.replace(tag, replacement)

        if len(safe_text) > max_length:
            safe_text = safe_text[:max_length] + "\n... (truncated for brevity)"

        return safe_text
