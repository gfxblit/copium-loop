from abc import ABC, abstractmethod

import psutil
from rich.text import Text

from ..codexbar import CodexbarClient


class FooterStatsStrategy(ABC):
    @abstractmethod
    def get_stats(self) -> list[Text | str | tuple[str, str]] | None:
        """Returns a list of rich renderables (strings or tuples for styling)."""
        pass


class CodexStatsStrategy(FooterStatsStrategy):
    def __init__(self, client: CodexbarClient):
        self.client = client

    def get_stats(self) -> list[Text | str | tuple[str, str]] | None:
        data = self.client.get_usage()
        if not data:
            return None

        # Calculate remaining
        pro = data.get("pro", 0)
        flash = data.get("flash", 0)
        reset_pro = data.get("reset_pro", data.get("reset", "?"))
        reset_flash = data.get("reset_flash", "?")

        remaining_pro = max(0, 100 - pro)
        remaining_flash = max(0, 100 - flash)

        stats = [
            (f"PRO LEFT: {remaining_pro:.1f}%", "bright_green"),
            "  ",
            (f"FLASH LEFT: {remaining_flash:.1f}%", "bright_yellow"),
            "  ",
        ]

        if reset_pro == reset_flash or reset_flash == "?":
            stats.append((f"RESET: {reset_pro}", "cyan"))
        else:
            stats.append((f"PRO RESET: {reset_pro}", "cyan"))
            stats.append("  ")
            stats.append((f"FLASH RESET: {reset_flash}", "cyan"))

        return stats


class SystemStatsStrategy(FooterStatsStrategy):
    def get_stats(self) -> list[Text | str | tuple[str, str]] | None:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent

        return [
            (f"CPU: {cpu}%", "bright_green"),
            "  ",
            (f"MEM: {mem}%", "bright_cyan"),
        ]
