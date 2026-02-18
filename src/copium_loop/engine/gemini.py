import os

from copium_loop.constants import COMMAND_TIMEOUT, INACTIVITY_TIMEOUT, MODELS
from copium_loop.engine.base import LLMEngine
from copium_loop.shell import stream_subprocess
from copium_loop.telemetry import get_telemetry


class GeminiEngine(LLMEngine):
    """Concrete implementation of LLMEngine using Gemini CLI."""

    @property
    def engine_type(self) -> str:
        return "gemini"

    async def _execute_gemini(
        self,
        prompt: str,
        model: str | None,
        args: list[str] | None = None,
        node: str | None = None,
        command_timeout: int | None = None,
        inactivity_timeout: int | None = None,
    ) -> str:
        """Internal method to execute the Gemini CLI with a specific model."""
        if command_timeout is None:
            command_timeout = COMMAND_TIMEOUT

        if inactivity_timeout is None:
            inactivity_timeout = INACTIVITY_TIMEOUT

        if args is None:
            args = []

        cmd_args = ["--sandbox"] + args
        if model:
            cmd_args.extend(["-m", model])

        cmd_args.extend(["-p", prompt])

        # Prevent interactive prompts in sub-agents
        env = os.environ.copy()
        env.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_EDITOR": "true",
                "EDITOR": "true",
                "VISUAL": "true",
                "GIT_SEQUENCE_EDITOR": "true",
                "GH_PROMPT_DISABLED": "1",
            }
        )

        output, exit_code, timed_out, timeout_message = await stream_subprocess(
            "gemini",
            cmd_args,
            env,
            node,
            command_timeout,
            inactivity_timeout=inactivity_timeout,
            capture_stderr=True,
        )

        if timed_out:
            raise Exception(f"[TIMEOUT] Gemini CLI timed out: {timeout_message}")

        if exit_code != 0:
            raise Exception(f"Gemini CLI exited with code {exit_code}\nOutput:\n{output}")

        return output.strip()

    async def invoke(
        self,
        prompt: str,
        args: list[str] | None = None,
        models: list[str | None] | None = None,
        verbose: bool = False,
        label: str | None = None,
        node: str | None = None,
        command_timeout: int | None = None,
        inactivity_timeout: int | None = None,
        jules_metadata: dict[str, str] | None = None,  # noqa: ARG002
    ) -> str:
        """
        Invokes the Gemini CLI with a prompt, supporting model fallback.
        Streams output to stdout and returns the full response.
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

        if args is None:
            args = []
        model_list = models if models is not None else MODELS
        for i, model in enumerate(model_list):
            try:
                model_display = model if model else "auto"
                if verbose:
                    print(f"Using model: {model_display}")
                return await self._execute_gemini(
                    prompt,
                    model,
                    args,
                    node,
                    command_timeout=command_timeout,
                    inactivity_timeout=inactivity_timeout,
                )
            except Exception as error:
                error_msg = str(error)
                is_last_model = i == len(model_list) - 1

                # Always fallback to next model on any error (unless it's the last model)
                if not is_last_model:
                    next_model = model_list[i + 1]
                    next_model_display = next_model if next_model else "auto"
                    print(f"Error with {model_display}: {error_msg}")
                    print(f"Falling back to {next_model_display}...")
                    continue

                # If we're on the last model and it failed, raise the error
                raise Exception(
                    f"All models exhausted. Last error: {error_msg}"
                ) from error
        return ""

    def sanitize_for_prompt(self, text: str, max_length: int = 12000) -> str:
        """
        Sanitizes untrusted text for inclusion in a prompt to prevent injection.
        Escapes common delimiters and truncates excessively long input.
        """
        if not text:
            return ""

        # Escape common XML-like tags to prevent prompt injection breakouts
        # We replace <tag> with [tag] and </tag> with [/tag]
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

    def get_required_tools(self) -> list[str]:
        """Returns a list of required CLI tools for the Gemini engine."""
        return ["gemini"]
