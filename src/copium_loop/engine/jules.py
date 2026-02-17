import asyncio
import os

import httpx

from copium_loop.engine.base import LLMEngine
from copium_loop.git import get_current_branch, get_repo_name, pull
from copium_loop.telemetry import get_telemetry


class JulesError(Exception):
    """Base exception for JulesEngine."""


class JulesSessionError(JulesError):
    """Raised when a Jules session fails or cannot be created."""


class JulesTimeoutError(JulesError):
    """Raised when a Jules operation times out."""


class JulesRepoError(JulesError):
    """Raised when the git repository name cannot be detected."""


# Constants for Jules API interactions
API_BASE_URL = "https://jules.googleapis.com/v1alpha"
POLLING_INTERVAL = 10
MAX_PROMPT_LENGTH = 12000


class JulesEngine(LLMEngine):
    """Concrete implementation of LLMEngine using Jules API."""

    async def invoke(
        self,
        prompt: str,
        _args: list[str] | None = None,
        _models: list[str | None] | None = None,
        verbose: bool = False,
        label: str | None = None,
        node: str | None = None,
        command_timeout: int | None = None,
        _inactivity_timeout: int | None = None,
    ) -> str:
        """
        Invokes the Jules API to create a remote session, polls for completion,
        and returns the result.
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

        try:
            repo = await get_repo_name(node=node)
        except ValueError as e:
            raise JulesRepoError(str(e)) from e

        branch = await get_current_branch(node=node)

        api_key = os.environ.get("JULES_API_KEY")
        if not api_key:
            raise JulesSessionError("JULES_API_KEY environment variable is not set.")

        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

        # Sanitize prompt to prevent injection
        safe_prompt = self.sanitize_for_prompt(prompt)

        # 1. Create session
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "prompt": safe_prompt,
                "sourceContext": {
                    "repository": repo,
                    "branch": branch,
                },
            }

            resp = await client.post(
                f"{API_BASE_URL}/sessions",
                headers=headers,
                json=payload,
            )

            if resp.status_code != 201:
                raise JulesSessionError(
                    f"Jules session creation failed with status {resp.status_code}: {resp.text}"
                )

            session_data = resp.json()
            session_name = session_data["name"]  # e.g., "sessions/sess_123"

            if verbose:
                print(f"Jules session created: {session_name}")

            # 2. Poll for completion
            start_time = asyncio.get_running_loop().time()
            timeout = command_timeout if command_timeout is not None else 300  # Default 5 minutes

            while True:
                if asyncio.get_running_loop().time() - start_time > timeout:
                     raise JulesTimeoutError("Jules operation timed out.")

                resp = await client.get(
                    f"{API_BASE_URL}/{session_name}",
                    headers=headers,
                )
                if resp.status_code != 200:
                    raise JulesSessionError(
                        f"Failed to poll Jules session {session_name}: {resp.status_code}"
                    )

                status_data = resp.json()
                state = status_data.get("state")

                if state == "COMPLETED":
                    # 3. Extract results
                    outputs = status_data.get("outputs", {})
                    summary = outputs.get("summary")
                    pr_url = outputs.get("pr_url")

                    if not summary:
                        # Fallback to activities if summary is not in outputs
                        activities = status_data.get("activities", [])
                        for activity in reversed(activities):
                            if "text" in activity:
                                summary = activity["text"]
                                break

                    if pr_url:
                        summary = (
                            f"{summary}\n\nPR Created: {pr_url}"
                            if summary
                            else f"PR Created: {pr_url}"
                        )

                    # 4. Pull changes locally if possible
                    try:
                        await pull(node=node)
                    except Exception as e:
                        if verbose:
                            print(
                                f"Warning: Failed to pull changes after Jules completion: {e}"
                            )

                    return summary or "Jules task completed, but no summary was found."

                if state == "FAILED":
                    raise JulesSessionError(f"Jules session {session_name} failed.")

                await asyncio.sleep(POLLING_INTERVAL)

    def sanitize_for_prompt(
        self, text: str, max_length: int = MAX_PROMPT_LENGTH
    ) -> str:
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
