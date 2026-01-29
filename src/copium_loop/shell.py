import asyncio
import contextlib
import os
import re
import subprocess
import sys
import time

from copium_loop.constants import (
    COMMAND_TIMEOUT,
    INACTIVITY_TIMEOUT,
    MAX_OUTPUT_SIZE,
)
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


class ProcessMonitor:
    """Monitors a subprocess for total timeout and inactivity timeout."""

    def __init__(
        self,
        process: asyncio.subprocess.Process,
        start_time: float,
        command_timeout: int | None,
        inactivity_timeout: int,
        node: str | None,
        on_timeout_callback=None,
    ):
        self.process = process
        self.start_time = start_time
        self.command_timeout = command_timeout
        self.inactivity_timeout = inactivity_timeout
        self.node = node
        self.on_timeout_callback = on_timeout_callback
        self.last_activity_time = time.monotonic()
        self.timed_out = False
        self.timeout_message = ""

    def update_activity(self):
        """Updates the last activity time."""
        self.last_activity_time = time.monotonic()

    async def run(self):
        """Runs the monitoring loop."""
        while True:
            await asyncio.sleep(0.1)
            if self.process.returncode is not None:
                break

            current_time = time.monotonic()
            elapsed_total_time = current_time - self.start_time
            elapsed_inactivity_time = current_time - self.last_activity_time

            timeout_triggered = False

            if (
                self.command_timeout is not None
                and elapsed_total_time >= self.command_timeout
            ):
                timeout_triggered = True
                self.timeout_message = (
                    f"Process exceeded command_timeout of {self.command_timeout}s."
                )
            elif elapsed_inactivity_time >= self.inactivity_timeout:
                timeout_triggered = True
                self.timeout_message = f"No output for {self.inactivity_timeout}s."

            if timeout_triggered:
                self.timed_out = True
                try:
                    self.process.kill()
                    msg = f"\n[TIMEOUT] {self.timeout_message} Killing process.\n"
                    print(msg)
                    telemetry = get_telemetry()
                    if telemetry and self.node:
                        telemetry.log_output(self.node, msg)

                    if self.on_timeout_callback:
                        if asyncio.iscoroutinefunction(self.on_timeout_callback):
                            await self.on_timeout_callback(msg)
                        else:
                            self.on_timeout_callback(msg)
                except Exception as e:
                    print(f"\n[WARNING] Failed to kill process or log timeout: {e}\n")
                break


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


async def stream_subprocess(
    command: str,
    args: list[str],
    env: dict,
    node: str | None,
    command_timeout: int | None,
    capture_stderr: bool = True,
    on_timeout_callback=None,
) -> tuple[str, int, bool, str]:
    """
    Common helper to execute a subprocess and stream its output.
    Returns (full_output, exit_code, timed_out, timeout_message).
    """
    start_time = time.monotonic()
    stderr_target = subprocess.PIPE if capture_stderr else subprocess.DEVNULL

    process = await asyncio.create_subprocess_exec(
        command, *args, stdout=subprocess.PIPE, stderr=stderr_target, env=env
    )

    full_output = ""
    logger = StreamLogger(node)

    monitor = ProcessMonitor(
        process,
        start_time,
        command_timeout,
        INACTIVITY_TIMEOUT,
        node,
        on_timeout_callback=on_timeout_callback,
    )
    monitor_task = asyncio.create_task(monitor.run())

    async def read_stream(stream, is_stderr):
        nonlocal full_output
        while True:
            chunk = await stream.read(1024)
            if not chunk:
                break
            monitor.update_activity()
            decoded = _clean_chunk(chunk)
            if decoded:
                if not is_stderr:
                    logger.process_chunk(decoded)

                # Limit capture size to prevent memory exhaustion
                if len(full_output) < MAX_OUTPUT_SIZE:
                    full_output += decoded
                    if len(full_output) >= MAX_OUTPUT_SIZE:
                        full_output = (
                            full_output[:MAX_OUTPUT_SIZE]
                            + "\n[... Output Truncated ...]"
                        )

    try:
        tasks = [read_stream(process.stdout, False)]
        if capture_stderr:
            tasks.append(read_stream(process.stderr, True))
        tasks.append(process.wait())
        await asyncio.gather(*tasks)
    finally:
        if not monitor_task.done():
            monitor_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await monitor_task

        # Ensure process is killed if it's still running (e.g., on cancellation)
        if process.returncode is None:
            try:
                process.kill()
                await process.wait()
            except ProcessLookupError:
                # Process already terminated
                pass

    logger.flush()

    if monitor.timed_out:
        exit_code = -1
    else:
        # Ensure returncode is an integer, default to 0 if None
        exit_code = process.returncode if process.returncode is not None else 0

    return full_output, exit_code, monitor.timed_out, monitor.timeout_message


async def run_command(
    command: str,
    args: list[str] | None = None,
    node: str | None = None,
    command_timeout: int | None = None,
) -> dict:
    """
    Invokes a shell command and streams output to stdout.
    Returns the combined stdout/stderr output and exit code.
    If command_timeout is provided, the process will be killed if it runs longer than command_timeout.
    If inactivity_timeout is exceeded (no output for INACTIVITY_TIMEOUT seconds), the process will be killed.
    """
    if command_timeout is None:
        command_timeout = COMMAND_TIMEOUT

    if args is None:
        args = []

    # Prevent interactive prompts that would hang the agent
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

    # Use a list to capture output from the callback
    timeout_msg_list = []

    async def on_timeout(msg):
        timeout_msg_list.append(msg)

    output, exit_code, _, _ = await stream_subprocess(
        command,
        args,
        env,
        node,
        command_timeout,
        capture_stderr=True,
        on_timeout_callback=on_timeout,
    )

    # Combine streamed output with any timeout message
    full_output = output
    if timeout_msg_list:
        full_output += "".join(timeout_msg_list)

    return {"output": full_output, "exit_code": exit_code}
