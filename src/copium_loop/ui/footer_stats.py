from abc import ABC, abstractmethod

from rich.text import Text

from ..gemini_stats import GeminiStatsClient


class FooterStatsStrategy(ABC):
    @abstractmethod
    def get_stats(self) -> list[Text | str | tuple[str, str]] | None:
        """Returns a list of rich renderables (strings or tuples for styling)."""
        pass


class GeminiStatsStrategy(FooterStatsStrategy):
    def __init__(self, client: GeminiStatsClient):
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

        # The values in 'pro' and 'flash' are now 'used' percentages
        pro = data.get("pro", 0)
        flash = data.get("flash", 0)
        reset_pro = data.get("reset_pro", data.get("reset", "?"))
        reset_flash = data.get("reset_flash", "?")

        stats = [
            (f"PRO USED: {pro:.1f}%", "bright_green"),
            "  ",
            (f"FLASH USED: {flash:.1f}%", "bright_yellow"),
            "  ",
        ]

        if reset_pro == reset_flash or reset_flash == "?":
            stats.append((f"RESET: {reset_pro}", "cyan"))
        else:
            stats.append((f"PRO RESET: {reset_pro}", "bright_green"))
            stats.append("  ")
            stats.append((f"FLASH RESET: {reset_flash}", "bright_yellow"))

        return stats
