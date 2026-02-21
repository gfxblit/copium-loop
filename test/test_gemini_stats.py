import unittest
from unittest.mock import MagicMock, patch

from copium_loop.gemini_stats import GeminiStatsClient


class TestGeminiStatsClient(unittest.TestCase):
    def setUp(self):
        self.client = GeminiStatsClient()
        # Reset cache for each test
        self.client._cached_data = None
        self.client._last_check = 0

    @patch("subprocess.run")
    def test_ensure_worker_creates_window_if_missing(self, mock_run):
        # Mock tmux list-windows to NOT show 'stats'
        mock_run.side_effect = [
            MagicMock(stdout="0: bash* (1 panes) [200x50]\n", returncode=0), # list-windows
            MagicMock(returncode=0), # new-window
        ]

        self.client._ensure_worker()

        # Check if tmux new-window was called
        mock_run.assert_any_call(
            [
                "tmux",
                "new-window",
                "-t",
                "copium-loop",
                "-n",
                "stats",
                "-d",
                "zsh -i -c '/opt/homebrew/bin/gemini --sandbox'",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_get_usage_success(self, mock_run):
        # Mock tmux behavior:
        # 1. list-windows (shows stats)
        # 2-5. send-keys (Escape, C-c, i, /stats)
        # 6. capture-pane
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
        mock_run.side_effect = [
            MagicMock(stdout="stats\n", returncode=0), # list-windows
            MagicMock(returncode=0), # send Escape
            MagicMock(returncode=0), # send C-c
            MagicMock(returncode=0), # send i
            MagicMock(returncode=0), # send /stats
            MagicMock(stdout=stats_output, returncode=0), # capture-pane
        ]

        with patch("time.sleep", return_value=None):
            usage = self.client.get_usage()

        self.assertIsNotNone(usage)
        # 80.0% remaining means 20.0% used.
        self.assertAlmostEqual(usage["pro"], 20.0)
        # 26.3% remaining means 73.7% used.
        self.assertAlmostEqual(usage["flash"], 73.7)
        self.assertEqual(usage["reset_pro"], "12h 25m")
        self.assertEqual(usage["reset_flash"], "12h 17m")

        # Verify 6 calls were made
        self.assertEqual(mock_run.call_count, 6)

    @patch("subprocess.run")
    def test_caching(self, mock_run):
        # Mock successful fetch first
        stats_output = """
│  gemini-3-pro-preview           -      100.0% resets in 1h                                                                            │
│  gemini-3-flash-preview         -      100.0% resets in 1h                                                                            │
"""
        mock_run.side_effect = [
            MagicMock(stdout="stats\n", returncode=0), # list-windows
            MagicMock(returncode=0), # send Escape
            MagicMock(returncode=0), # send C-c
            MagicMock(returncode=0), # send i
            MagicMock(returncode=0), # send /stats
            MagicMock(stdout=stats_output, returncode=0), # capture-pane
        ]

        with patch("time.sleep", return_value=None):
            self.client.get_usage()

        self.assertEqual(mock_run.call_count, 6)

        # Second call should use cache
        self.client.get_usage()
        self.assertEqual(mock_run.call_count, 6) # Still 6

if __name__ == "__main__":
    unittest.main()
