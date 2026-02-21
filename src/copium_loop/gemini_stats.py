#!/usr/bin/env python3
from __future__ import annotations
import asyncio
import json
import re
import subprocess
import sys
import time


class GeminiStatsClient:
    """
    Client for interacting with the gemini-cli inside a tmux window
    to fetch usage quotas via /stats.
    """

    def __init__(self, session_name: str = "copium-loop"):
        self.session_name = session_name
        self.window_name = "stats"
        self.target = f"{self.session_name}:{self.window_name}"
        self._cache_ttl = 60
        self._last_check = 0
        self._cached_data: dict | None = None

    def _ensure_worker(self):
        """Ensures the background gemini-cli session is running in tmux."""
        try:
            # Check if the window exists using a more robust list-windows call
            result = subprocess.run(
                ["tmux", "list-windows", "-a", "-F", "#{session_name}:#{window_name}"],
                capture_output=True,
                text=True,
                check=False,
            )
            target_entry = f"{self.session_name}:{self.window_name}"
            if target_entry not in result.stdout:
                # Create window and start gemini
                # Use absolute path for gemini.
                cmd = "/opt/homebrew/bin/gemini --sandbox"
                subprocess.run(
                    [
                        "tmux",
                        "new-window",
                        "-t",
                        self.session_name,
                        "-n",
                        self.window_name,
                        "-d",
                        cmd,
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                # Give it a few seconds to initialize
                time.sleep(3.0)
        except Exception:
            pass

    def get_usage(self) -> dict | None:
        """
        Fetches usage statistics by querying the background gemini session.
        Returns a dictionary with 'pro', 'flash', and 'reset' keys, or None if failed.
        """
        now = time.time()
        if self._cached_data and (now - self._last_check < self._cache_ttl):
            return self._cached_data

        self._ensure_worker()

        try:
            # Send robust sequence to trigger /stats:
            # 1. Escape to ensure we're in Normal mode
            # 2. C-c to clear any partial input
            # 3. 'i' to enter Insert mode
            # 4. '/stats' and Enter to execute
            subprocess.run(
                ["tmux", "send-keys", "-t", self.target, "Escape"],
                check=False,
            )
            time.sleep(0.1)
            subprocess.run(
                ["tmux", "send-keys", "-t", self.target, "C-c"],
                check=False,
            )
            time.sleep(0.1)
            subprocess.run(
                ["tmux", "send-keys", "-t", self.target, "i"],
                check=False,
            )
            time.sleep(0.1)
            subprocess.run(
                ["tmux", "send-keys", "-t", self.target, "/stats", "Enter"],
                check=False,
            )

            # Wait for output to be generated and rendered
            time.sleep(1.5)

            # Capture pane output
            result = subprocess.run(
                ["tmux", "capture-pane", "-p", "-t", self.target],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                return None

            return self._parse_output(result.stdout)

        except Exception:
            return None

    async def get_usage_async(self) -> dict | None:
        """
        Asynchronously fetches usage statistics.
        """
        # For simplicity in this implementation, we'll wrap the sync call
        # as the interaction with tmux is mostly shell-based and quick.
        return await asyncio.to_thread(self.get_usage)

    def _parse_output(self, output: str) -> dict:
        """
        Parses the /stats output to extract usage percentages and reset times.
        """
        data = {
            "pro": 0.0,
            "flash": 0.0,
            "reset": "?",
            "reset_pro": "?",
            "reset_flash": "?",
        }

        # Pro models in priority order
        for model in ["gemini-3-pro-preview", "gemini-2.5-pro"]:
            pro_match = re.search(
                rf"{model}\s+(?:-|\d+)\s+([\d\.]+)%\s+resets in\s+([^│\n\r]+)",
                output,
                re.IGNORECASE,
            )
            if pro_match:
                remaining = float(pro_match.group(1))
                data["pro"] = 100.0 - remaining
                data["reset_pro"] = pro_match.group(2).strip()
                data["reset"] = data["reset_pro"]
                break

        # Flash models in priority order
        for model in ["gemini-3-flash-preview", "gemini-2.5-flash"]:
            flash_match = re.search(
                rf"{model}\s+(?:-|\d+)\s+([\d\.]+)%\s+resets in\s+([^│\n\r]+)",
                output,
                re.IGNORECASE,
            )
            if flash_match:
                remaining = float(flash_match.group(1))
                data["flash"] = 100.0 - remaining
                data["reset_flash"] = flash_match.group(2).strip()
                break

        if data["pro"] > 0 or data["flash"] > 0 or data["reset"] != "?":
            self._cached_data = data
            self._last_check = time.time()

        return data


if __name__ == "__main__":
    # Allow passing session name as first argument
    session = sys.argv[1] if len(sys.argv) > 1 else "copium-loop"
    client = GeminiStatsClient(session_name=session)
    usage = client.get_usage()
    if usage:
        print(json.dumps(usage, indent=2))
    else:
        print(json.dumps({"error": "Failed to fetch usage"}, indent=2))
        sys.exit(1)
