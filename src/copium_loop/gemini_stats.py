#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
import time
from typing import Protocol, runtime_checkable

from copium_loop.tmux import TmuxInterface, TmuxManager

logger = logging.getLogger(__name__)


@runtime_checkable
class StatsFetcher(Protocol):
    """Protocol for fetching raw stats output."""

    def fetch(self) -> str | None:
        """Fetches the raw string output from the stats source."""
        ...

    async def fetch_async(self) -> str | None:
        """Asynchronously fetches the raw string output."""
        ...


class TmuxStatsFetcher:
    """Fetches stats by interacting with gemini-cli inside a tmux window."""

    def __init__(
        self,
        session_name: str = "copium-loop",
        window_name: str = "stats",
        tmux: TmuxInterface | None = None,
        gemini_cmd: str = "/opt/homebrew/bin/gemini --sandbox",
    ):
        self.session_name = session_name
        self.window_name = window_name
        self.target = f"{self.session_name}:{self.window_name}"
        self.tmux = tmux or TmuxManager()
        self.gemini_cmd = gemini_cmd

    def _ensure_worker(self):
        """Ensures the background gemini-cli session is running in tmux."""
        try:
            if not self.tmux.has_window(self.session_name, self.window_name):
                self.tmux.new_window(
                    self.session_name,
                    self.window_name,
                    self.gemini_cmd,
                )
                time.sleep(10.0)
        except Exception:
            pass

    def fetch(self) -> str | None:
        self._ensure_worker()
        try:
            self.tmux.send_keys(self.target, "Escape")
            time.sleep(0.1)
            self.tmux.send_keys(self.target, "C-c")
            time.sleep(0.1)
            self.tmux.send_keys(self.target, "i")
            time.sleep(0.1)
            self.tmux.send_keys(self.target, "/stats")
            time.sleep(0.1)
            self.tmux.send_keys(self.target, "Enter")

            time.sleep(2.0)
            output = self.tmux.capture_pane(self.target)
            return output if output else None
        except Exception as e:
            logger.error("Failed to fetch stats from tmux: %s", str(e))
            return None

    async def fetch_async(self) -> str | None:
        return await asyncio.to_thread(self.fetch)


class GeminiStatsClient:
    """
    Client for fetching and parsing usage quotas.
    Decoupled from the actual fetching mechanism via StatsFetcher.
    """

    def __init__(
        self,
        fetcher: StatsFetcher | None = None,
        # Keep these for backward compatibility
        session_name: str = "copium-loop",
        tmux: TmuxInterface | None = None,
        gemini_cmd: str | None = None,
    ):
        if fetcher:
            self.fetcher = fetcher
        else:
            fetcher_kwargs = {"session_name": session_name, "tmux": tmux}
            if gemini_cmd:
                fetcher_kwargs["gemini_cmd"] = gemini_cmd
            self.fetcher = TmuxStatsFetcher(**fetcher_kwargs)

        self._cache_ttl = 60
        self._last_check = 0
        self._cached_data: dict | None = None
        self._lock = asyncio.Lock()

    def get_usage(self) -> dict | None:
        """
        Fetches usage statistics.
        Returns a dictionary with 'pro', 'flash', and 'reset' keys, or None if failed.
        """
        now = time.time()
        if self._cached_data and (now - self._last_check < self._cache_ttl):
            return self._cached_data

        try:
            output = self.fetcher.fetch()
            if not output:
                return None

            return self._parse_output(output)
        except Exception as e:
            logger.error("Failed to get usage: %s", str(e))
            return None

    async def get_usage_async(self) -> dict | None:
        """Asynchronously fetches usage statistics."""
        async with self._lock:
            now = time.time()
            if self._cached_data and (now - self._last_check < self._cache_ttl):
                return self._cached_data

            try:
                output = await self.fetcher.fetch_async()
                if not output:
                    return None

                return self._parse_output(output)
            except Exception as e:
                logger.error("Failed to get usage async: %s", str(e))
                return None

    def _parse_output(self, output: str) -> dict:
        """Parses the raw output to extract usage percentages and reset times."""
        data = {
            "pro": 0.0,
            "flash": 0.0,
            "reset": "?",
            "reset_pro": "?",
            "reset_flash": "?",
        }

        # Pro models in priority order
        for model in ["gemini-3.1-pro-preview", "gemini-2.5-pro"]:
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
