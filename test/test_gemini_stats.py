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
            MagicMock(stdout="bash\n", returncode=0),  # list-windows
            MagicMock(returncode=0),  # new-window
        ]

        with patch("time.sleep", return_value=None) as mock_sleep:
            self.client._ensure_worker()
            # Verify it sleeps for 10 seconds
            mock_sleep.assert_called_with(10.0)

        # Check if tmux list-windows was called with session target and format
        mock_run.assert_any_call(
            ["tmux", "list-windows", "-t", "copium-loop", "-F", "#{window_name}"],
            capture_output=True,
            text=True,
            check=False,
        )

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
                "/opt/homebrew/bin/gemini --sandbox",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_get_usage_success(self, mock_run):
        # Mock tmux behavior:
        # 1. list-windows (shows stats)
        # 2-6. send-keys (Escape, C-c, i, /stats, Enter)
        # 7. capture-pane
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
            MagicMock(stdout="stats\n", returncode=0),  # list-windows
            MagicMock(returncode=0),  # send Escape
            MagicMock(returncode=0),  # send C-c
            MagicMock(returncode=0),  # send i
            MagicMock(returncode=0),  # send /stats
            MagicMock(returncode=0),  # send Enter
            MagicMock(stdout=stats_output, returncode=0),  # capture-pane
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

        # Verify 7 calls were made
        self.assertEqual(mock_run.call_count, 7)

        # Verify all send-keys calls use the fully qualified target
        target = "copium-loop:stats"
        mock_run.assert_any_call(
            ["tmux", "send-keys", "-t", target, "Escape"], check=False
        )
        mock_run.assert_any_call(
            ["tmux", "send-keys", "-t", target, "C-c"], check=False
        )
        mock_run.assert_any_call(["tmux", "send-keys", "-t", target, "i"], check=False)
        mock_run.assert_any_call(
            ["tmux", "send-keys", "-t", target, "/stats"], check=False
        )
        mock_run.assert_any_call(
            ["tmux", "send-keys", "-t", target, "Enter"], check=False
        )
        mock_run.assert_any_call(
            ["tmux", "capture-pane", "-p", "-t", target],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_caching(self, mock_run):
        # Mock successful fetch first
        stats_output = """
│  gemini-3-pro-preview           -      100.0% resets in 1h                                                                            │
│  gemini-3-flash-preview         -      100.0% resets in 1h                                                                            │
"""
        mock_run.side_effect = [
            MagicMock(stdout="stats\n", returncode=0),  # list-windows
            MagicMock(returncode=0),  # send Escape
            MagicMock(returncode=0),  # send C-c
            MagicMock(returncode=0),  # send i
            MagicMock(returncode=0),  # send /stats
            MagicMock(returncode=0),  # send Enter
            MagicMock(stdout=stats_output, returncode=0),  # capture-pane
        ]

        with patch("time.sleep", return_value=None):
            self.client.get_usage()

        self.assertEqual(mock_run.call_count, 7)

        # Second call should use cache
        self.client.get_usage()
        self.assertEqual(mock_run.call_count, 7)  # Still 7

    @patch("subprocess.run")
    def test_ensure_worker_handles_multiple_sessions(self, mock_run):
        # Create client with specific session name
        client = GeminiStatsClient(session_name="test-session")
        # Mock tmux list-windows to return windows from different sessions
        # But our code uses -t test-session, so it should only see windows from that session.
        mock_run.side_effect = [
            MagicMock(
                stdout="bash\nother-window\n", returncode=0
            ),  # list-windows -t test-session
            MagicMock(returncode=0),  # new-window
        ]

        with patch("time.sleep", return_value=None):
            client._ensure_worker()

        # Check if tmux list-windows was called with the correct session
        mock_run.assert_any_call(
            ["tmux", "list-windows", "-t", "test-session", "-F", "#{window_name}"],
            capture_output=True,
            text=True,
            check=False,
        )

        # Check if tmux new-window was called with the correct session
        mock_run.assert_any_call(
            [
                "tmux",
                "new-window",
                "-t",
                "test-session",
                "-n",
                "stats",
                "-d",
                "/opt/homebrew/bin/gemini --sandbox",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    @patch("subprocess.run")
    def test_get_usage_with_sufficient_delay(self, mock_run):
        # Mock successful fetch
        stats_output = "gemini-3-pro-preview 0 100.0% resets in 1h"
        mock_run.side_effect = [
            MagicMock(stdout="stats\n", returncode=0),  # list-windows
            MagicMock(returncode=0),  # send Escape
            MagicMock(returncode=0),  # send C-c
            MagicMock(returncode=0),  # send i
            MagicMock(returncode=0),  # send /stats
            MagicMock(returncode=0),  # send Enter
            MagicMock(stdout=stats_output, returncode=0),  # capture-pane
        ]

        with patch("time.sleep", return_value=None) as mock_sleep:
            self.client.get_usage()

            # Verify the delay after Enter before capture-pane is sufficient
            # We want it to be 2.0s.
            sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
            self.assertIn(2.0, sleep_calls)

    @patch("copium_loop.gemini_stats.logger")
    @patch("subprocess.run")
    def test_get_usage_logs_error(self, mock_run, mock_logger):
        # Mock subprocess.run raising an exception
        mock_run.side_effect = Exception("Tmux error")

        with patch("time.sleep", return_value=None):
            usage = self.client.get_usage()

        self.assertIsNone(usage)
        mock_logger.error.assert_called_with("Failed to fetch stats: %s", "Tmux error")


if __name__ == "__main__":
    unittest.main()
