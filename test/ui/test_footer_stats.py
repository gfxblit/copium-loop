from unittest.mock import MagicMock

from copium_loop.ui.footer_stats import CodexStatsStrategy


class TestCodexStatsStrategy:
    def test_get_stats_shows_both_resets(self):
        # Mock CodexbarClient
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {
            "pro": 85,
            "flash": 40,
            "reset": "18:30",
            "reset_pro": "18:30",
            "reset_flash": "19:45",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        # Convert stats to plain text for easy assertion
        plain_texts = []
        for item in stats:
            if isinstance(item, tuple):
                plain_texts.append(item[0])
            elif isinstance(item, str):
                plain_texts.append(item)
            else:  # Rich Text
                plain_texts.append(item.plain)

        full_text = "".join(plain_texts)

        # We expect to see both reset times
        assert "PRO RESET: 18:30" in full_text
        assert "FLASH RESET: 19:45" in full_text

    def test_get_stats_shows_single_reset_when_same(self):
        # Mock CodexbarClient
        mock_client = MagicMock()
        mock_client.get_usage.return_value = {
            "pro": 85,
            "flash": 40,
            "reset": "18:30",
            "reset_pro": "18:30",
            "reset_flash": "18:30",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        plain_texts = []
        for item in stats:
            if isinstance(item, tuple):
                plain_texts.append(item[0])
            elif isinstance(item, str):
                plain_texts.append(item)
            else:  # Rich Text
                plain_texts.append(item.plain)

        full_text = "".join(plain_texts)

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
            "reset": "18:30",
            "reset_pro": "18:30",
            "reset_flash": "?",
        }

        strategy = CodexStatsStrategy(mock_client)
        stats = strategy.get_stats()

        plain_texts = []
        for item in stats:
            if isinstance(item, tuple):
                plain_texts.append(item[0])
            elif isinstance(item, str):
                plain_texts.append(item)
            else:  # Rich Text
                plain_texts.append(item.plain)

        full_text = "".join(plain_texts)

        # We expect to see only one reset entry
        assert "RESET: 18:30" in full_text
        assert "PRO RESET:" not in full_text
