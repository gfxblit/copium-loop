import unittest
from unittest.mock import MagicMock, patch

from copium_loop.gemini_stats import GeminiStatsClient, TmuxStatsFetcher


class TestTmuxStatsFetcher(unittest.IsolatedAsyncioTestCase):
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

        # Verify exact sequence of send-keys calls
        target = "copium-loop:stats"
        from unittest.mock import call

        expected_calls = [
            call(target, "Escape"),
            call(target, "C-c"),
            call(target, "i"),
            call(target, "/stats"),
            call(target, "Enter"),
        ]
        self.mock_tmux.send_keys.assert_has_calls(expected_calls)

    @patch("copium_loop.gemini_stats.logger")
    def test_fetch_logs_error(self, mock_logger):
        self.mock_tmux.send_keys.side_effect = Exception("Tmux error")

        with patch("time.sleep", return_value=None):
            output = self.fetcher.fetch()

        self.assertIsNone(output)
        mock_logger.error.assert_called_with(
            "Failed to fetch stats from tmux: %s", "Tmux error"
        )

    async def test_fetch_async(self):
        # Mock tmux behavior
        self.mock_tmux.has_window.return_value = True
        stats_output = "gemini-3-pro-preview 0 80.0% resets in 1h"
        self.mock_tmux.capture_pane.return_value = stats_output

        with patch("time.sleep", return_value=None):
            output = await self.fetcher.fetch_async()

        self.assertEqual(output, stats_output)

    def test_ensure_worker_exception_handled(self):
        # Mock has_window to raise exception
        self.mock_tmux.has_window.side_effect = Exception("Tmux connection failed")

        # Should not raise exception
        self.fetcher._ensure_worker()

        self.mock_tmux.has_window.assert_called()


class TestGeminiStatsClient(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_fetcher = MagicMock()
        self.mock_fetcher.fetch_async = unittest.mock.AsyncMock()
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

    def test_get_usage_failure(self):
        self.mock_fetcher.fetch.return_value = None
        usage = self.client.get_usage()
        self.assertIsNone(usage)

    @patch("copium_loop.gemini_stats.logger")
    def test_get_usage_exception(self, mock_logger):
        self.mock_fetcher.fetch.side_effect = Exception("Fetch error")
        usage = self.client.get_usage()
        self.assertIsNone(usage)
        mock_logger.error.assert_called_with("Failed to get usage: %s", "Fetch error")

    async def test_get_usage_async_success(self):
        stats_output = "gemini-3-pro-preview 0 80.0% resets in 1h"
        self.mock_fetcher.fetch_async.return_value = stats_output

        usage = await self.client.get_usage_async()

        self.assertIsNotNone(usage)
        self.assertAlmostEqual(usage["pro"], 20.0)

    async def test_get_usage_async_failure(self):
        self.mock_fetcher.fetch_async.return_value = None
        usage = await self.client.get_usage_async()
        self.assertIsNone(usage)

    @patch("copium_loop.gemini_stats.logger")
    async def test_get_usage_async_exception(self, mock_logger):
        self.mock_fetcher.fetch_async.side_effect = Exception("Async error")
        usage = await self.client.get_usage_async()
        self.assertIsNone(usage)
        mock_logger.error.assert_called_with(
            "Failed to get usage async: %s", "Async error"
        )

    def test_caching(self):
        # Mock successful fetch first
        self.mock_fetcher.fetch.return_value = (
            "gemini-3-pro-preview 0 100.0% resets in 1h"
        )

        self.client.get_usage()
        self.assertEqual(self.mock_fetcher.fetch.call_count, 1)

        # Second call should use cache
        self.client.get_usage()
        self.assertEqual(self.mock_fetcher.fetch.call_count, 1)  # Still 1

    async def test_caching_async(self):
        # Mock successful fetch first
        self.mock_fetcher.fetch_async.return_value = (
            "gemini-3-pro-preview 0 100.0% resets in 1h"
        )

        await self.client.get_usage_async()
        self.assertEqual(self.mock_fetcher.fetch_async.call_count, 1)

        # Second call should use cache
        await self.client.get_usage_async()
        self.assertEqual(self.mock_fetcher.fetch_async.call_count, 1)

    def test_parse_output_flash(self):
        stats_output = "gemini-3-flash-preview 0 70.0% resets in 30m"
        self.mock_fetcher.fetch.return_value = stats_output

        usage = self.client.get_usage()
        self.assertAlmostEqual(usage["flash"], 30.0)
        self.assertEqual(usage["reset_flash"], "30m")

    def test_backward_compatibility(self):
        mock_tmux = MagicMock()
        client = GeminiStatsClient(session_name="test-session", tmux=mock_tmux)

        # Verify it created a TmuxStatsFetcher with the right parameters
        self.assertIsInstance(client.fetcher, TmuxStatsFetcher)
        self.assertEqual(client.fetcher.session_name, "test-session")
        self.assertEqual(client.fetcher.tmux, mock_tmux)

    def test_gemini_cmd_config(self):
        client = GeminiStatsClient(gemini_cmd="/custom/gemini")
        self.assertIsInstance(client.fetcher, TmuxStatsFetcher)
        self.assertEqual(client.fetcher.gemini_cmd, "/custom/gemini")


if __name__ == "__main__":
    unittest.main()
