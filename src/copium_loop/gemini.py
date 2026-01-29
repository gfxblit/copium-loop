import os

from copium_loop.constants import COMMAND_TIMEOUT, DEFAULT_MODELS
from copium_loop.shell import stream_subprocess


async def _execute_gemini(
    prompt: str,
    model: str | None,
    args: list[str] | None = None,
    node: str | None = None,
    command_timeout: int | None = None,
) -> str:
    """Internal method to execute the Gemini CLI with a specific model."""
    if command_timeout is None:
        command_timeout = COMMAND_TIMEOUT

    if args is None:
        args = []

    cmd_args = ["--sandbox"] + args
    if model:
        cmd_args.extend(["-m", model])

    cmd_args.append(prompt)

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
        capture_stderr=False,
    )

    if timed_out:
        raise Exception(f"[TIMEOUT] Gemini CLI timed out: {timeout_message}")

    if exit_code != 0:
        raise Exception(f"Gemini CLI exited with code {exit_code}")

    return output.strip()


async def invoke_gemini(
    prompt: str,
    args: list[str] | None = None,
    models: list[str | None] | None = None,
    verbose: bool = False,
    label: str | None = None,
    node: str | None = None,
    command_timeout: int | None = None,
) -> str:
    """
    Invokes the Gemini CLI with a prompt, supporting model fallback.
    Streams output to stdout and returns the full response.
    """
    if verbose:
        banner = (
            f"--- [VERBOSE] {label} Prompt ---" if label else "--- [VERBOSE] Prompt ---"
        )
        print(f"\n{banner}")
        print(prompt)
        print("-" * len(banner) + "\n")

    if args is None:
        args = []
    model_list = models if models is not None else DEFAULT_MODELS
    for i, model in enumerate(model_list):
        try:
            model_display = model if model else "auto"
            if verbose:
                print(f"Using model: {model_display}")
            return await _execute_gemini(
                prompt, model, args, node, command_timeout=command_timeout
            )
        except Exception as error:
            error_msg = str(error)
            is_last_model = i == len(model_list) - 1

            # Always fallback to next model on any error (unless it's the last model)
            # This handles quota errors, rate limits, and other transient failures
            if not is_last_model:
                next_model = model_list[i + 1]
                next_model_display = next_model if next_model else "auto"
                print(f"Error with {model_display}: {error_msg}")
                # If it's a timeout, we might want to log it specifically but still fallback
                print(f"Falling back to {next_model_display}...")
                continue

            # If we're on the last model and it failed, raise the error
            raise Exception(f"All models exhausted. Last error: {error_msg}") from error
    return ""
