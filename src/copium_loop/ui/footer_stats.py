from abc import ABC, abstractmethod

import psutil
from rich.text import Text

from ..codexbar import CodexbarClient


def generate_spark_bar(percentage: float, width: int = 10) -> str:
    """Generates a text-based spark bar."""
    normalized = max(0, min(100, percentage))
    step = 100 / width
    return "".join(["█" if i < normalized / step else " " for i in range(width)])


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
        reset = data.get("reset", "?")

        remaining_pro = max(0, 100 - pro)
        remaining_flash = max(0, 100 - flash)

        pro_spark = generate_spark_bar(remaining_pro)
        flash_spark = generate_spark_bar(remaining_flash)

        return [
            (f"PRO LEFT: {remaining_pro}%", "bright_green"),
            f" [{pro_spark}] ",
            "  ",
            (f"FLASH LEFT: {remaining_flash}%", "bright_yellow"),
            f" [{flash_spark}] ",
            "  ",
            (f"RESET: {reset}", "cyan"),
        ]


class SystemStatsStrategy(FooterStatsStrategy):
    def get_stats(self) -> list[Text | str | tuple[str, str]] | None:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        spark = generate_spark_bar(cpu)  # CPU usage, not remaining

        return [
            (f"CPU: {cpu}%", "bright_green"),
            f" [{spark}] ",
            "  ",
            (f"MEM: {mem}%", "bright_cyan"),
        ]
