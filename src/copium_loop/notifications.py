import asyncio
import os
import subprocess

from copium_loop.shell import run_command


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
