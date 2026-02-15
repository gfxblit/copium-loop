from abc import ABC, abstractmethod

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
        return self._format_stats(data)

    async def get_stats_async(self) -> list[Text | str | tuple[str, str]] | None:
        data = await self.client.get_usage_async()
        return self._format_stats(data)

    def _format_stats(
        self, data: dict | None
    ) -> list[Text | str | tuple[str, str]] | None:
        if data is None:
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
            stats.append((f"PRO RESET: {reset_pro}", "bright_green"))
            stats.append("  ")
            stats.append((f"FLASH RESET: {reset_flash}", "bright_yellow"))

        return stats
