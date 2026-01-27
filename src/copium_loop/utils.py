import asyncio
import contextlib
import os
import re
import subprocess
import sys
import time
import unittest.mock

from copium_loop.constants import DEFAULT_MODELS, INACTIVITY_TIMEOUT
from copium_loop.telemetry import get_telemetry


class StreamLogger:
    """Helper to buffer output for line-based logging while streaming to stdout."""

    def __init__(self, node: str | None):
        self.node = node
        self.buffer = ""
        self.telemetry = get_telemetry() if node else None

    def process_chunk(self, chunk: str):
        """Streams chunk to stdout immediately and buffers for telemetry."""
        if not chunk:
            return

        sys.stdout.write(chunk)
        sys.stdout.flush()

        if self.telemetry:
            self.buffer += chunk
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                self.telemetry.log_output(self.node, line + "\n")

    def flush(self):
        """Flushes any remaining buffered output to telemetry."""
        if self.telemetry and self.buffer:
            self.telemetry.log_output(self.node, self.buffer)
            self.buffer = ""


def _clean_chunk(chunk: str | bytes) -> str:
    """
    Cleans a chunk of output by removing null bytes, non-printable control
    characters, and ANSI escape codes.
    """
    if isinstance(chunk, bytes):
        try:
            chunk = chunk.decode("utf-8", errors="replace")
        except Exception:
            return ""

    if not isinstance(chunk, str):
        return str(chunk)

    # Remove ANSI escape codes
    without_ansi = re.sub(r"\x1B\[[0-9;]*[a-zA-Z]", "", chunk)

    # Remove disruptive control characters (excluding TAB, LF, CR)
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", without_ansi)


async def run_command(
    command: str,
    args: list[str] | None = None,
    node: str | None = None,
    total_timeout: int | None = None,
) -> dict:
    """
    Invokes a shell command and streams output to stdout.
    Returns the combined stdout/stderr output and exit code.
    If total_timeout is provided, the process will be killed if it runs longer than total_timeout.
    If inactivity_timeout is exceeded (no output for INACTIVITY_TIMEOUT seconds), the process will be killed.
    """
    if args is None:
        args = []

    # Prevent interactive prompts that would hang the agent
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_EDITOR"] = "true"
    env["EDITOR"] = "true"
    env["VISUAL"] = "true"
    env["GIT_SEQUENCE_EDITOR"] = "true"
    env["GH_PROMPT_DISABLED"] = "1"

    start_time = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        command, *args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )

    full_output = ""
    stdout_logger = StreamLogger(node)
    last_activity_time = time.monotonic()
    timed_out = False

    async def read_stream(stream, is_stderr):
        nonlocal full_output, last_activity_time
        while True:
            line = await stream.read(1024)
            if not line:
                break
            last_activity_time = time.monotonic()
            decoded_chunk = _clean_chunk(line)
            if decoded_chunk:
                if not is_stderr:
                    stdout_logger.process_chunk(decoded_chunk)
                full_output += decoded_chunk

    async def monitor_timeout():
        nonlocal last_activity_time, timed_out, full_output
        while True:
            await asyncio.sleep(0.1)
            if process.returncode is not None:
                break

            current_time = time.monotonic()
            elapsed_total_time = current_time - start_time
            elapsed_inactivity_time = current_time - last_activity_time

            timeout_triggered = False
            timeout_message = ""

            if total_timeout is not None and elapsed_total_time >= total_timeout:
                timeout_triggered = True
                timeout_message = f"Process exceeded total_timeout of {total_timeout}s."
            elif elapsed_inactivity_time >= INACTIVITY_TIMEOUT:
                timeout_triggered = True
                timeout_message = f"No output for {INACTIVITY_TIMEOUT}s."

            if timeout_triggered:
                timed_out = True
                try:
                    process.kill()
                    msg = f"\n[TIMEOUT] {timeout_message} Killing process.\n"
                    full_output += msg
                    print(msg)
                    telemetry = get_telemetry()
                    if telemetry and node:
                        telemetry.log_output(node, msg)
                except Exception:
                    pass
                break

    monitor_task = asyncio.create_task(monitor_timeout())

    try:
        await asyncio.gather(
            read_stream(process.stdout, False),
            read_stream(process.stderr, True),
            process.wait(),
        )
    finally:
        if not monitor_task.done():
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task

    stdout_logger.flush()
    if timed_out:
        exit_code = -1
    else:
        exit_code = process.returncode
        # Ensure exit_code is an integer, even if it's a mock in tests
        if exit_code is None or isinstance(exit_code, unittest.mock.AsyncMock):
            exit_code = 0

    return {"output": full_output, "exit_code": exit_code}


async def _execute_gemini(
    prompt: str,
    model: str | None,
    args: list[str] | None = None,
    node: str | None = None,
    total_timeout: int | None = None,
) -> str:
    """Internal method to execute the Gemini CLI with a specific model."""
    if args is None:
        args = []

    cmd_args = ["--sandbox"] + args
    if model:
        cmd_args.extend(["-m", model])

    cmd_args.append(prompt)

    # Prevent interactive prompts in sub-agents
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_EDITOR"] = "true"
    env["EDITOR"] = "true"
    env["VISUAL"] = "true"
    env["GIT_SEQUENCE_EDITOR"] = "true"
    env["GH_PROMPT_DISABLED"] = "1"

    start_time = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        "gemini", *cmd_args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env
    )

    full_output = ""
    logger = StreamLogger(node)
    last_activity_time = time.monotonic()
    timed_out = False
    timeout_message = ""

    async def read_stdout():
        nonlocal full_output, last_activity_time
        while True:
            chunk = await process.stdout.read(1024)
            if not chunk:
                break
            last_activity_time = time.monotonic()
            decoded = _clean_chunk(chunk)
            if decoded:
                logger.process_chunk(decoded)
                full_output += decoded

    async def monitor_timeout():
        nonlocal last_activity_time, timed_out, timeout_message
        while True:
            await asyncio.sleep(0.1)
            if process.returncode is not None:
                break

            current_time = time.monotonic()
            elapsed_total_time = current_time - start_time
            elapsed_inactivity_time = current_time - last_activity_time

            timeout_triggered = False

            if total_timeout is not None and elapsed_total_time >= total_timeout:
                timeout_triggered = True
                timeout_message = f"Process exceeded total_timeout of {total_timeout}s."
            elif elapsed_inactivity_time >= INACTIVITY_TIMEOUT:
                timeout_triggered = True
                timeout_message = f"No output for {INACTIVITY_TIMEOUT}s."

            if timeout_triggered:
                timed_out = True
                try:
                    process.kill()
                    msg = f"\n[TIMEOUT] {timeout_message} Killing process.\n"
                    print(msg)
                    telemetry = get_telemetry()
                    if telemetry and node:
                        telemetry.log_output(node, msg)
                except Exception:
                    pass
                break

    monitor_task = asyncio.create_task(monitor_timeout())

    try:
        await asyncio.gather(read_stdout(), process.wait())
    finally:
        if not monitor_task.done():
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task

    logger.flush()
    # If the process was timed out, we override the exit code to -1
    if timed_out:
        exit_code = -1
    else:
        exit_code = process.returncode
        # Ensure exit_code is an integer, even if it's a mock in tests
        if exit_code is None or isinstance(exit_code, unittest.mock.AsyncMock):
            # If process.wait() returned, it implies the process finished,
            # so a default of 0 (success) is reasonable if no specific code is available.
            # If timed_out is True, this block won't be reached.
            exit_code = 0

    if timed_out:
        raise Exception(f"[TIMEOUT] Gemini CLI timed out: {timeout_message}")

    if exit_code != 0:
        raise Exception(f"Gemini CLI exited with code {exit_code}")

    return full_output.strip()


async def invoke_gemini(
    prompt: str,
    args: list[str] | None = None,
    models: list[str | None] | None = None,
    verbose: bool = False,
    label: str | None = None,
    node: str | None = None,
    total_timeout: int | None = INACTIVITY_TIMEOUT,
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
                prompt, model, args, node, total_timeout=total_timeout
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


async def get_tmux_session() -> str:
    """Retrieves the current tmux session name."""
    try:
        process = await asyncio.create_subprocess_exec(
            "tmux",
            "display-message",
            "-p",
            "#S",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        output = stdout.decode().strip()
        if output:
            return output
    except Exception:
        pass
    return "no-tmux"


async def notify(title: str, message: str, priority: int = 3):
    """Sends a notification to ntfy.sh if NTFY_CHANNEL is set."""
    channel = os.environ.get("NTFY_CHANNEL")
    if not channel:
        return

    session_name = await get_tmux_session()
    full_message = f"Session: {session_name}\n{message}"

    try:
        await run_command(
            "curl",
            [
                "-sS",
                "-H",
                f"Title: {title}",
                "-H",
                f"Priority: {priority}",
                "-d",
                full_message,
                f"https://ntfy.sh/{channel}",
            ],
        )
    except Exception as e:
        print(f"Failed to send notification: {e}")


def get_package_manager() -> str:
    """Detects the package manager based on lock files."""
    if os.path.exists("pnpm-lock.yaml"):
        return "pnpm"
    if os.path.exists("yarn.lock"):
        return "yarn"
    return "npm"


def get_test_command() -> tuple[str, list[str]]:
    """Determines the test command based on the project structure."""
    test_cmd = "npm"
    test_args = ["test"]

    if os.environ.get("COPIUM_TEST_CMD"):
        parts = os.environ.get("COPIUM_TEST_CMD").split()
        test_cmd = parts[0]
        test_args = parts[1:]
    elif os.path.exists("package.json"):
        test_cmd = get_package_manager()
        test_args = ["test"]
    elif (
        os.path.exists("pyproject.toml")
        or os.path.exists("setup.py")
        or os.path.exists("requirements.txt")
    ):
        test_cmd = "pytest"
        test_args = ["--cov=src", "--cov-report=term-missing"]

    return test_cmd, test_args


def get_build_command() -> tuple[str, list[str]]:
    """Determines the build command based on the project structure."""
    build_cmd = "npm"
    build_args = ["run", "build"]

    if os.environ.get("COPIUM_BUILD_CMD"):
        parts = os.environ.get("COPIUM_BUILD_CMD").split()
        build_cmd = parts[0]
        build_args = parts[1:]
    elif os.path.exists("package.json"):
        build_cmd = get_package_manager()
        build_args = ["run", "build"]
    elif (
        os.path.exists("pyproject.toml")
        or os.path.exists("setup.py")
        or os.path.exists("requirements.txt")
    ):
        # For Python, build often means building the package or just checking types/compiling
        # If there's no explicit build command, we might just return None or a placeholder
        # For now, let's see if there's a common one. Often it's just 'pip install -e .' or 'python -m build'
        # But if we don't know, we'll return None to signal skipping build.
        return "", []

    return build_cmd, build_args


def get_lint_command() -> tuple[str, list[str]]:
    """Determines the lint command based on the project structure."""
    lint_cmd = "npm"
    lint_args = ["run", "lint"]

    if os.environ.get("COPIUM_LINT_CMD"):
        parts = os.environ.get("COPIUM_LINT_CMD").split()
        lint_cmd = parts[0]
        lint_args = parts[1:]
    elif os.path.exists("package.json"):
        lint_cmd = get_package_manager()
        lint_args = ["run", "lint"]
    elif (
        os.path.exists("pyproject.toml")
        or os.path.exists("setup.py")
        or os.path.exists("requirements.txt")
    ):
        lint_cmd = "ruff"
        lint_args = ["check", "."]

    return lint_cmd, lint_args
