import asyncio
import contextlib
import os
import re
import subprocess
import sys
import time

from copium_loop.constants import (
    COMMAND_TIMEOUT,
    INACTIVITY_TIMEOUT,  # noqa: F401
    MAX_OUTPUT_SIZE,
)
from copium_loop.telemetry import get_telemetry

# Pre-compile regexes for performance
ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-9;]*[a-zA-Z]")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


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
    """Monitors a subprocess for total command timeout and inactivity timeout."""

    def __init__(
        self,
        process: asyncio.subprocess.Process,
        start_time: float,
        command_timeout: float | None,
        inactivity_timeout: float | None,
        node: str | None,
        on_timeout_callback=None,
    ):
        self.process = process
        self.start_time = start_time
        self.command_timeout = command_timeout
        self.inactivity_timeout = inactivity_timeout
        self.node = node
        self.on_timeout_callback = on_timeout_callback
        self.last_activity = time.monotonic()
        self.timed_out = False
        self.timeout_message = ""

    def update_activity(self):
        """Resets the inactivity timer."""
        self.last_activity = time.monotonic()

    async def run(self):
        """Polls the process until it finishes or a timeout occurs."""
        while self.process.returncode is None:
            now = time.monotonic()

            # Check for command timeout
            if self.command_timeout and (now - self.start_time) > self.command_timeout:
                self.timed_out = True
                self.timeout_message = (
                    f"Process exceeded command_timeout of {self.command_timeout}s."
                )
                break

            # Check for inactivity timeout
            if (
                self.inactivity_timeout
                and (now - self.last_activity) > self.inactivity_timeout
            ):
                self.timed_out = True
                self.timeout_message = (
                    f"No output for {self.inactivity_timeout}s "
                    f"(inactivity_timeout exceeded)."
                )
                break

            await asyncio.sleep(0.1)

        if self.timed_out:
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

            if self.process.returncode is None:
                try:
                    self.process.kill()
                except ProcessLookupError:
                    pass
                except Exception as e:
                    print(
                        f"[WARNING] Error during process kill on timeout: {e}",
                        file=sys.stderr,
                    )


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
    without_ansi = ANSI_ESCAPE_RE.sub("", chunk)

    # Remove disruptive control characters (excluding TAB, LF, CR)
    return CONTROL_CHAR_RE.sub("", without_ansi)


async def stream_subprocess(
    command: str,
    args: list[str],
    env: dict,
    node: str | None,
    command_timeout: int | None,
    inactivity_timeout: int | None = None,
    capture_stderr: bool = True,
    on_timeout_callback=None,
) -> tuple[str, int, bool, str]:
    """
    Common helper to execute a subprocess and stream its output.
    Returns (full_output, exit_code, timed_out, timeout_message).
    """
    stderr_target = subprocess.PIPE if capture_stderr else subprocess.DEVNULL

    process = await asyncio.create_subprocess_exec(
        command, *args, stdout=subprocess.PIPE, stderr=stderr_target, env=env
    )

    full_output = ""
    output_chunks = []
    current_output_size = 0
    truncated = False
    logger = StreamLogger(node)
    start_time = time.monotonic()

    monitor = ProcessMonitor(
        process,
        start_time,
        command_timeout=command_timeout,
        inactivity_timeout=inactivity_timeout,
        node=node,
        on_timeout_callback=on_timeout_callback,
    )

    async def read_stream(stream, is_stderr):
        nonlocal current_output_size, truncated
        while True:
            try:
                chunk = await stream.read(1024)
            except (asyncio.CancelledError, Exception):
                break
            if not chunk:
                break

            monitor.update_activity()
            decoded = _clean_chunk(chunk)
            if decoded:
                if not is_stderr:
                    logger.process_chunk(decoded)

                if not truncated and current_output_size < MAX_OUTPUT_SIZE:
                    output_chunks.append(decoded)
                    current_output_size += len(decoded)
                    if current_output_size >= MAX_OUTPUT_SIZE:
                        full_output_temp = "".join(output_chunks)
                        output_chunks.clear()
                        output_chunks.append(full_output_temp[:MAX_OUTPUT_SIZE])
                        output_chunks.append("\n[... Output Truncated ...]")
                        truncated = True

    read_stdout_task = asyncio.create_task(read_stream(process.stdout, False))
    read_stderr_task = None
    if capture_stderr:
        read_stderr_task = asyncio.create_task(read_stream(process.stderr, True))

    monitor_task = asyncio.create_task(monitor.run())

    try:
        wait_task = asyncio.create_task(process.wait())
        done, pending = await asyncio.wait(
            [wait_task, monitor_task], return_when=asyncio.FIRST_COMPLETED
        )

        # If monitor_task completed first (meaning a timeout occurred),
        # ensure wait_task is cancelled.
        if monitor_task in done and wait_task in pending:
            wait_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await wait_task  # Await to clean up the task

    except asyncio.CancelledError:
        # If the stream_subprocess task itself is cancelled, ensure we kill the process
        if process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
        raise
    finally:
        # Final cleanup: ensure process is reaped and monitor/readers are stopped
        if process.returncode is None:
            try:
                process.kill()
                # Use communicate() wrapped in wait_for to avoid hanging on pipes held by descendants
                with contextlib.suppress(asyncio.TimeoutError, Exception):
                    await asyncio.wait_for(process.communicate(), timeout=0.5)
            except (ProcessLookupError, Exception):
                pass

        # Stop reader tasks and monitor task
        for task in [read_stdout_task, read_stderr_task, monitor_task]:
            if (
                task
            ):  # Only attempt to cancel and await if the task was actually created
                if not task.done():
                    task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        logger.flush()

    full_output = "".join(output_chunks)

    if monitor.timed_out:
        exit_code = -1
    else:
        exit_code = process.returncode if process.returncode is not None else 0

    return full_output, exit_code, monitor.timed_out, monitor.timeout_message


async def run_command(
    command: str,
    args: list[str] | None = None,
    node: str | None = None,
    command_timeout: int | None = None,
    capture_stderr: bool = True,
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

    output, exit_code, timed_out, timeout_message = await stream_subprocess(
        command,
        args,
        env,
        node,
        command_timeout,
        inactivity_timeout=INACTIVITY_TIMEOUT,
        capture_stderr=capture_stderr,
        on_timeout_callback=on_timeout,
    )

    # Combine streamed output with any timeout message
    full_output = output
    final_exit_code = exit_code

    if timed_out:
        full_output += f"\n[TIMEOUT] {timeout_message}"
        if timeout_msg_list:
            full_output += "".join(timeout_msg_list)
        full_output += " Killing process.\n"
        final_exit_code = -1

    return {"output": full_output, "exit_code": final_exit_code}
