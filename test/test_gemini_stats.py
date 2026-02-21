import unittest
from unittest.mock import MagicMock, patch

from copium_loop.gemini_stats import GeminiStatsClient, TmuxStatsFetcher


class TestTmuxStatsFetcher(unittest.TestCase):
    def setUp(self):
        self.mock_tmux = MagicMock()
        self.fetcher = TmuxStatsFetcher(tmux=self.mock_tmux)

    def test_ensure_worker_creates_window_if_missing(self):
        # Mock tmux behavior: window missing
        self.mock_tmux.has_window.return_value = False

        with patch("time.sleep", return_value=None) as mock_sleep:
            self.fetcher._ensure_worker()
            # Verify it sleeps for 10 seconds
            mock_sleep.assert_called_with(10.0)

        # Check if has_window was called
        self.mock_tmux.has_window.assert_called_with("copium-loop", "stats")

        # Check if new_window was called
        self.mock_tmux.new_window.assert_called_with(
            "copium-loop", "stats", "/opt/homebrew/bin/gemini --sandbox"
        )

    def test_fetch_success(self):
        # Mock tmux behavior
        self.mock_tmux.has_window.return_value = True
        stats_output = "gemini-3-pro-preview 0 80.0% resets in 1h"
        self.mock_tmux.capture_pane.return_value = stats_output

        with patch("time.sleep", return_value=None):
            output = self.fetcher.fetch()

        self.assertEqual(output, stats_output)
        
        # Verify send-keys calls
        target = "copium-loop:stats"
        self.mock_tmux.send_keys.assert_any_call(target, "Escape")
        self.mock_tmux.send_keys.assert_any_call(target, "Enter")

    @patch("copium_loop.gemini_stats.logger")
    def test_fetch_logs_error(self, mock_logger):
        self.mock_tmux.send_keys.side_effect = Exception("Tmux error")

        with patch("time.sleep", return_value=None):
            output = self.fetcher.fetch()

        self.assertIsNone(output)
        mock_logger.error.assert_called_with("Failed to fetch stats from tmux: %s", "Tmux error")


class TestGeminiStatsClient(unittest.TestCase):
    def setUp(self):
        self.mock_fetcher = MagicMock()
        self.client = GeminiStatsClient(fetcher=self.mock_fetcher)
        # Reset cache for each test
        self.client._cached_data = None
        self.client._last_check = 0

    def test_get_usage_success(self):
        stats_output = """
│  gemini-3-pro-preview           -      80.0% resets in 12h 25m                                                                            │
"""
        self.mock_fetcher.fetch.return_value = stats_output

        usage = self.client.get_usage()

        self.assertIsNotNone(usage)
        # 80.0% remaining means 20.0% used.
        self.assertAlmostEqual(usage["pro"], 20.0)
        self.assertEqual(usage["reset_pro"], "12h 25m")

    def test_caching(self):
        # Mock successful fetch first
        self.mock_fetcher.fetch.return_value = "gemini-3-pro-preview 0 100.0% resets in 1h"

        self.client.get_usage()
        self.assertEqual(self.mock_fetcher.fetch.call_count, 1)

        # Second call should use cache
        self.client.get_usage()
        self.assertEqual(self.mock_fetcher.fetch.call_count, 1)  # Still 1

    def test_backward_compatibility(self):
        mock_tmux = MagicMock()
        client = GeminiStatsClient(session_name="test-session", tmux=mock_tmux)
        
        # Verify it created a TmuxStatsFetcher with the right parameters
        self.assertIsInstance(client.fetcher, TmuxStatsFetcher)
        self.assertEqual(client.fetcher.session_name, "test-session")
        self.assertEqual(client.fetcher.tmux, mock_tmux)


if __name__ == "__main__":
    unittest.main()
