import asyncio
import os

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from copium_loop.constants import COMMAND_TIMEOUT, INACTIVITY_TIMEOUT
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

    def __init__(self, api_base_url: str = API_BASE_URL):
        self.api_base_url = api_base_url

    def _get_headers(self) -> dict[str, str]:
        """Returns the headers required for Jules API calls."""
        api_key = os.environ.get("JULES_API_KEY")
        if not api_key:
            raise JulesSessionError("JULES_API_KEY environment variable is not set.")

        return {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

    async def _request_with_retry(
        self, context: str, func, *args, **kwargs
    ) -> httpx.Response:
        """Helper to retry a network request with exponential backoff using tenacity."""
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(4),
                wait=wait_exponential(multiplier=2, min=1, max=10),
                retry=retry_if_exception_type(httpx.HTTPError),
                reraise=True,
            ):
                with attempt:
                    return await func(*args, **kwargs)
        except httpx.HTTPError as e:
            raise JulesSessionError(f"{context}: {e}") from e

        # This part should be unreachable due to reraise=True and return in the loop
        raise JulesSessionError("Request failed unexpectedly.")

    async def _create_session(
        self, client: httpx.AsyncClient, prompt: str, repo: str, branch: str
    ) -> str:
        """Creates a new Jules session and returns its name."""
        # Map repo "owner/repo" to "sources/github/owner/repo"
        source_name = f"sources/github/{repo}"

        payload = {
            "prompt": prompt,
            "sourceContext": {
                "source": source_name,
                "githubRepoContext": {
                    "startingBranch": branch,
                },
            },
        }

        resp = await self._request_with_retry(
            "Network error creating Jules session",
            client.post,
            f"{self.api_base_url}/sessions",
            headers=self._get_headers(),
            json=payload,
        )

        if resp.status_code not in (200, 201):
            raise JulesSessionError(
                f"Jules session creation failed with status {resp.status_code}: {resp.text}"
            )

        session_data = resp.json()
        return session_data["name"]

    async def _poll_session(
        self,
        client: httpx.AsyncClient,
        session_name: str,
        timeout: int,
        inactivity_timeout: int,
        node: str | None = None,
        verbose: bool = False,
    ) -> dict:
        """Polls the Jules session until completion or timeout."""
        start_time = asyncio.get_running_loop().time()
        last_activity_time = start_time
        seen_activities = set()
        telemetry = get_telemetry()
        last_summary = ""

        while True:
            current_time = asyncio.get_running_loop().time()
            if current_time - start_time > timeout:
                raise JulesTimeoutError(
                    f"Jules operation timed out (total timeout: {timeout}s)."
                )

            if current_time - last_activity_time > inactivity_timeout:
                raise JulesTimeoutError(
                    f"Jules operation timed out (inactivity timeout: {inactivity_timeout}s)."
                )

            # 1. Fetch activities to show progress
            try:
                act_resp = await self._request_with_retry(
                    "Network error fetching activities",
                    client.get,
                    f"{self.api_base_url}/{session_name}/activities",
                    headers=self._get_headers(),
                )
                if act_resp.status_code == 200:
                    activities = act_resp.json().get("activities", [])
                    new_activity_found = False
                    for activity in activities:
                        act_id = activity.get("id")
                        if act_id and act_id not in seen_activities:
                            seen_activities.add(act_id)
                            new_activity_found = True

                            # Extract progress information
                            title = ""
                            desc = ""
                            if "progressUpdated" in activity:
                                title = activity["progressUpdated"].get("title", "")
                                desc = activity["progressUpdated"].get(
                                    "description", ""
                                )
                            elif "planGenerated" in activity:
                                title = "Plan generated"
                                plan = activity["planGenerated"].get("plan", {})
                                steps = plan.get("steps", [])
                                if steps:
                                    desc = f"{len(steps)} steps planned"
                            elif "toolCallStarted" in activity:
                                tool_call = activity["toolCallStarted"]
                                title = f"Tool Call: {tool_call.get('toolName')}"
                                args = tool_call.get("args")
                                if args:
                                    desc = str(args)
                            elif "toolCallCompleted" in activity:
                                tool_resp = activity["toolCallCompleted"]
                                title = (
                                    f"Tool Call Completed: {tool_resp.get('toolName')}"
                                )
                            elif "sessionCompleted" in activity:
                                title = "Session completed"
                            elif "sessionFailed" in activity:
                                title = "Session failed"
                                desc = activity["sessionFailed"].get("reason", "")

                            if not title:
                                # Fallback to top-level fields
                                title = (
                                    activity.get("description")
                                    or activity.get("text")
                                    or "Activity update"
                                )

                            msg = f"[{session_name}] {title}"
                            if desc:
                                msg += f": {desc}"

                            if verbose:
                                print(msg)
                            if node:
                                telemetry.log_output(node, msg + "\n")

                            # Update last_summary with any textual description we find
                            if title or desc:
                                last_summary = desc or title

                    if new_activity_found:
                        last_activity_time = current_time

            except Exception as e:
                if verbose:
                    print(f"Warning: Failed to fetch activities: {e}")

            # 2. Check session state
            resp = await self._request_with_retry(
                "Network error polling Jules session",
                client.get,
                f"{self.api_base_url}/{session_name}",
                headers=self._get_headers(),
            )

            if resp.status_code != 200:
                raise JulesSessionError(
                    f"Failed to poll Jules session {session_name}: {resp.status_code}"
                )

            status_data = resp.json()
            state = status_data.get("state")

            if state == "COMPLETED":
                # Inject the last seen summary into status_data for _extract_summary
                if last_summary and "activities" not in status_data:
                    status_data["activities"] = [{"description": last_summary}]
                return status_data
            if state == "FAILED":
                raise JulesSessionError(f"Jules session {session_name} failed.")

            await asyncio.sleep(POLLING_INTERVAL)

    def _extract_summary(self, status_data: dict) -> str:
        """Extracts the summary and PR URL from the completed session data."""
        outputs = status_data.get("outputs", [])
        summary = ""
        pr_url = ""

        # Extract pull request info from outputs array
        for output in outputs:
            if isinstance(output, dict) and "pullRequest" in output:
                pr = output["pullRequest"]
                pr_url = pr.get("url", "")
                title = pr.get("title", "")
                if not summary and title:
                    summary = title

        # Fallback to activities for textual summary if not already found
        activities = status_data.get("activities", [])
        if not summary:
            for activity in reversed(activities):
                # Check for description or other textual fields in activity
                text = activity.get("description") or activity.get("text")
                if text:
                    summary = text
                    break

        if pr_url:
            summary = (
                f"{summary}\n\nPR Created: {pr_url}"
                if summary
                else f"PR Created: {pr_url}"
            )

        return summary or "Jules task completed, but no summary was found."

    async def invoke(
        self,
        prompt: str,
        args: list[str] | None = None,  # noqa: ARG002
        models: list[str | None] | None = None,  # noqa: ARG002
        verbose: bool = False,
        label: str | None = None,
        node: str | None = None,
        command_timeout: int | None = None,
        inactivity_timeout: int | None = None,
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

        # Sanitize prompt to prevent injection
        safe_prompt = self.sanitize_for_prompt(prompt)

        timeout = command_timeout if command_timeout is not None else COMMAND_TIMEOUT
        inactivity = (
            inactivity_timeout if inactivity_timeout is not None else INACTIVITY_TIMEOUT
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Create session
            session_name = await self._create_session(client, safe_prompt, repo, branch)

            if verbose:
                print(f"Jules session created: {session_name}")

            # 2. Poll for completion
            status_data = await self._poll_session(
                client, session_name, timeout, inactivity, node, verbose
            )

            # 3. Extract results
            summary = self._extract_summary(status_data)

            # 4. Capture Jules text output via a designated file
            try:
                with open("JULES_OUTPUT.txt", "w", encoding="utf-8") as f:
                    f.write(summary)
            except Exception as e:
                if verbose:
                    print(f"Warning: Failed to write JULES_OUTPUT.txt: {e}")

            # 5. Pull changes locally if possible
            res = await pull(node=node)
            if res["exit_code"] != 0:
                raise JulesSessionError(
                    f"Failed to pull changes after Jules completion: {res['output']}"
                )

            return summary

    def get_required_tools(self) -> list[str]:
        """Returns a list of required CLI tools for the Jules engine."""
        return []

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
