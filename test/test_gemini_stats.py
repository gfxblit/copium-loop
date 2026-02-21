import unittest
from unittest.mock import MagicMock, patch

from copium_loop.gemini_stats import GeminiStatsClient


class TestGeminiStatsClient(unittest.TestCase):
    def setUp(self):
        self.mock_tmux = MagicMock()
        self.client = GeminiStatsClient(tmux=self.mock_tmux)
        # Reset cache for each test
        self.client._cached_data = None
        self.client._last_check = 0

    def test_ensure_worker_creates_window_if_missing(self):
        # Mock tmux behavior: window missing
        self.mock_tmux.has_window.return_value = False

        with patch("time.sleep", return_value=None) as mock_sleep:
            self.client._ensure_worker()
            # Verify it sleeps for 10 seconds
            mock_sleep.assert_called_with(10.0)

        # Check if has_window was called
        self.mock_tmux.has_window.assert_called_with("copium-loop", "stats")

        # Check if new_window was called
        self.mock_tmux.new_window.assert_called_with(
            "copium-loop", "stats", "/opt/homebrew/bin/gemini --sandbox"
        )

    def test_get_usage_success(self):
        # Mock tmux behavior:
        self.mock_tmux.has_window.return_value = True
        stats_output = """
│  Auto (Gemini 3) Usage                                                                                                                   │
│  Model                       Reqs             Usage remaining                                                                            │
│  ────────────────────────────────────────────────────────────                                                                            │
│  gemini-2.5-flash-lite          5     98.2% resets in 12h 25m                                                                            │
│  gemini-3-flash-preview        28     26.3% resets in 12h 17m                                                                            │
│  gemini-2.5-flash               -     26.3% resets in 12h 17m                                                                            │
│  gemini-2.5-pro                 -      0.0% resets in 12h 25m                                                                            │
│  gemini-3-pro-preview           -      80.0% resets in 12h 25m                                                                            │
"""
        self.mock_tmux.capture_pane.return_value = stats_output

        with patch("time.sleep", return_value=None):
            usage = self.client.get_usage()

        self.assertIsNotNone(usage)
        # 80.0% remaining means 20.0% used.
        self.assertAlmostEqual(usage["pro"], 20.0)
        # 26.3% remaining means 73.7% used.
        self.assertAlmostEqual(usage["flash"], 73.7)
        self.assertEqual(usage["reset_pro"], "12h 25m")
        self.assertEqual(usage["reset_flash"], "12h 17m")

        # Verify send-keys calls
        target = "copium-loop:stats"
        self.mock_tmux.send_keys.assert_any_call(target, "Escape")
        self.mock_tmux.send_keys.assert_any_call(target, "C-c")
        self.mock_tmux.send_keys.assert_any_call(target, "i")
        self.mock_tmux.send_keys.assert_any_call(target, "/stats")
        self.mock_tmux.send_keys.assert_any_call(target, "Enter")

        # Verify capture-pane call
        self.mock_tmux.capture_pane.assert_called_with(target)

    def test_caching(self):
        # Mock successful fetch first
        self.mock_tmux.has_window.return_value = True
        stats_output = """
│  gemini-3-pro-preview           -      100.0% resets in 1h                                                                            │
│  gemini-3-flash-preview         -      100.0% resets in 1h                                                                            │
"""
        self.mock_tmux.capture_pane.return_value = stats_output

        with patch("time.sleep", return_value=None):
            self.client.get_usage()

        self.assertEqual(self.mock_tmux.capture_pane.call_count, 1)

        # Second call should use cache
        self.client.get_usage()
        self.assertEqual(self.mock_tmux.capture_pane.call_count, 1)  # Still 1

    def test_ensure_worker_handles_multiple_sessions(self):
        # Create client with specific session name
        client = GeminiStatsClient(session_name="test-session", tmux=self.mock_tmux)
        self.mock_tmux.has_window.return_value = False

        with patch("time.sleep", return_value=None):
            client._ensure_worker()

        # Check if has_window was called with the correct session
        self.mock_tmux.has_window.assert_called_with("test-session", "stats")

        # Check if new_window was called with the correct session
        self.mock_tmux.new_window.assert_called_with(
            "test-session", "stats", "/opt/homebrew/bin/gemini --sandbox"
        )

    def test_get_usage_with_sufficient_delay(self):
        # Mock successful fetch
        self.mock_tmux.has_window.return_value = True
        stats_output = "gemini-3-pro-preview 0 100.0% resets in 1h"
        self.mock_tmux.capture_pane.return_value = stats_output

        with patch("time.sleep", return_value=None) as mock_sleep:
            self.client.get_usage()

            # Verify the delay after Enter before capture-pane is sufficient
            # We want it to be 2.0s.
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            self.assertIn(2.0, sleep_calls)

    @patch("copium_loop.gemini_stats.logger")
    def test_get_usage_logs_error(self, mock_logger):
        # Mock send_keys raising an exception (has_window exception is swallowed by _ensure_worker)
        self.mock_tmux.send_keys.side_effect = Exception("Tmux error")

        with patch("time.sleep", return_value=None):
            usage = self.client.get_usage()

        self.assertIsNone(usage)
        mock_logger.error.assert_called_with("Failed to fetch stats: %s", "Tmux error")


if __name__ == "__main__":
    unittest.main()
