from unittest.mock import MagicMock

import pytest
from rich.text import Text
from textual.css.scalar import Unit
from textual.widgets import Static

from copium_loop.ui.footer_stats import CodexStatsStrategy
from copium_loop.ui.textual_dashboard import TextualDashboard


class TestCodexStatsStrategy:
    def _stats_to_text(self, stats: list | None) -> str:
        """Helper to convert stats list to a single string for assertion."""
        if not stats:
            return ""
        plain_texts = []
        for item in stats:
            if isinstance(item, tuple):
                plain_texts.append(item[0])
            elif isinstance(item, str):
                plain_texts.append(item)
            else:  # Rich Text
                plain_texts.append(item.plain)
        return "".join(plain_texts)

    def test_get_stats_shows_both_resets(self):
        # Mock CodexbarClient
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {
            "pro": 85,
            "flash": 40,
            "reset_pro": "18:30",
            "reset_flash": "19:45",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()
        full_text = self._stats_to_text(stats)

        # We expect to see both reset times
        assert "PRO RESET: 18:30" in full_text
        assert "FLASH RESET: 19:45" in full_text

    def test_get_stats_shows_single_reset_when_same(self):
        # Mock CodexbarClient
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {
            "pro": 85,
            "flash": 40,
            "reset_pro": "18:30",
            "reset_flash": "18:30",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()
        full_text = self._stats_to_text(stats)

        # We expect to see only one reset entry
        assert "RESET: 18:30" in full_text
        assert "PRO RESET:" not in full_text
        assert "FLASH RESET:" not in full_text

    def test_get_stats_shows_single_reset_when_flash_unknown(self):
        # Mock CodexbarClient
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {
            "pro": 85,
            "flash": 40,
            "reset_pro": "18:30",
            "reset_flash": "?",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()
        full_text = self._stats_to_text(stats)

        # We expect to see only one reset entry
        assert "RESET: 18:30" in full_text
        assert "PRO RESET:" not in full_text

    def test_get_stats_success_legacy_reset(self):
        # Setup mock client with legacy 'reset' field
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {
            "pro": 20.5,
            "flash": 40.0,
            "reset": "2h 30m",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        assert stats is not None
        assert stats[0] == ("PRO LEFT: 79.5%", "bright_green")
        assert stats[2] == ("FLASH LEFT: 60.0%", "bright_yellow")
        # Since reset_flash defaults to '?' and reset_pro defaults to data.get('reset')
        assert stats[4] == ("RESET: 2h 30m", "cyan")

    def test_get_stats_none(self):
        # Setup mock client
        mock_client = MagicMock()
        mock_client.get_usage.return_value = None

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        assert stats is None

    def test_get_stats_zero_usage(self):
        # Setup mock client for 0% usage (100% left)
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {"pro": 0, "flash": 0, "reset": "never"}

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()
        assert stats[0][0] == "PRO LEFT: 100.0%"
        assert stats[2][0] == "FLASH LEFT: 100.0%"

    def test_get_stats_full_usage(self):
        # Setup mock client for 100% usage (0% left)
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {"pro": 100, "flash": 100, "reset": "now"}

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()
        assert stats[0][0] == "PRO LEFT: 0.0%"
        assert stats[2][0] == "FLASH LEFT: 0.0%"

    def test_get_stats_over_usage(self):
        # Setup mock client for >100% usage (0% left)
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {
            "pro": 120,
            "flash": 150,
            "reset": "long ago",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()
        assert stats[0][0] == "PRO LEFT: 0.0%"
        assert stats[2][0] == "FLASH LEFT: 0.0%"

    def test_get_stats_missing_fields(self):
        # Setup mock client with empty dict
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {}

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        assert stats is not None
        # Should use default 0 for pro/flash and '?' for reset
        assert stats[0][0] == "PRO LEFT: 100.0%"
        assert stats[2][0] == "FLASH LEFT: 100.0%"
        assert stats[4][0] == "RESET: ?"


@pytest.mark.asyncio
async def test_stats_bar_height_auto(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test():
        stats_bar = app.query_one("#stats-bar", Static)

        # Currently it has height: auto in CSS
        assert stats_bar.styles.height.unit == Unit.AUTO


@pytest.mark.asyncio
async def test_stats_bar_wraps_with_long_content(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)

    async with app.run_test() as pilot:
        # Set a very narrow width to force wrapping
        await pilot.resize_terminal(40, 24)
        stats_bar = app.query_one("#stats-bar", Static)

        # Inject long content
        long_text = Text(" ".join(["LONG_CONTENT"] * 20))
        stats_bar.update(long_text)
        await pilot.pause()

        # If height is auto, it should be more than 2 when it wraps
        assert stats_bar.region.height > 2


@pytest.mark.asyncio
async def test_system_stats_strategy_removed_from_dashboard(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)

    # Check that only CodexStatsStrategy is in stats_strategies
    strategies = [type(s) for s in app.stats_strategies]
    assert len(strategies) == 1
    assert strategies[0] == CodexStatsStrategy


@pytest.mark.asyncio
async def test_footer_does_not_contain_cpu_mem(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_footer_stats()
        await pilot.pause()

        stats_bar = app.query_one("#stats-bar", Static)
        renderable = stats_bar.render()
        content = renderable.plain if hasattr(renderable, "plain") else str(renderable)
        assert "CPU:" not in content
        assert "MEM:" not in content
