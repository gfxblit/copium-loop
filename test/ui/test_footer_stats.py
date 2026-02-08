from unittest.mock import MagicMock, patch

from copium_loop.ui.footer_stats import CodexStatsStrategy, SystemStatsStrategy


class TestCodexStatsStrategy:
    def test_get_stats_success(self):
        # Setup mock client
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {
            "pro": 20.5,
            "flash": 40.0,
            "reset": "2h 30m",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        assert stats is not None
        assert len(stats) == 5
        assert stats[0] == ("PRO LEFT: 79.5%", "bright_green")
        assert stats[2] == ("FLASH LEFT: 60.0%", "bright_yellow")
        assert stats[4] == ("RESET: 2h 30m", "cyan")

    def test_get_stats_none(self):
        # Setup mock client
        mock_client = MagicMock()
        mock_client.get_usage.return_value = None

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        assert stats is None

    def test_get_stats_edge_cases(self):
        # Setup mock client for 0% usage (100% left)
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {"pro": 0, "flash": 0, "reset": "never"}

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()
        assert stats[0][0] == "PRO LEFT: 100.0%"
        assert stats[2][0] == "FLASH LEFT: 100.0%"

        # Setup mock client for 100% usage (0% left)
        mock_client.get_usage.return_value = {"pro": 100, "flash": 100, "reset": "now"}
        stats = strategy.get_stats()
        assert stats[0][0] == "PRO LEFT: 0.0%"
        assert stats[2][0] == "FLASH LEFT: 0.0%"

        # Setup mock client for >100% usage (0% left)
        mock_client.get_usage.return_value = {
            "pro": 120,
            "flash": 150,
            "reset": "long ago",
        }
        stats = strategy.get_stats()
        assert stats[0][0] == "PRO LEFT: 0.0%"
        assert stats[2][0] == "FLASH LEFT: 0.0%"

    def test_get_stats_missing_fields(self):
        # Setup mock client with missing fields
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {}

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        # Should use default 0 for pro/flash and '?' for reset
        assert stats[0][0] == "PRO LEFT: 100.0%"
        assert stats[2][0] == "FLASH LEFT: 100.0%"
        assert stats[4][0] == "RESET: ?"


class TestSystemStatsStrategy:
    @patch("psutil.cpu_percent")
    @patch("psutil.virtual_memory")
    def test_get_stats(self, mock_virtual_memory, mock_cpu_percent):
        mock_cpu_percent.return_value = 15.5
        mock_mem = MagicMock()
        mock_mem.percent = 62.3
        mock_virtual_memory.return_value = mock_mem

        strategy = SystemStatsStrategy()
        stats = strategy.get_stats()

        assert stats is not None
        assert len(stats) == 3
        assert stats[0] == ("CPU: 15.5%", "bright_green")
        assert stats[1] == "  "
        assert stats[2] == ("MEM: 62.3%", "bright_cyan")
