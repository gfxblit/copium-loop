import unittest
from unittest.mock import MagicMock

from copium_loop.tmux import TmuxManager


class TestTmuxManager(unittest.TestCase):
    def setUp(self):
        self.mock_runner = MagicMock()
        self.tmux = TmuxManager(runner=self.mock_runner)

    def test_list_windows(self):
        self.mock_runner.run.return_value = MagicMock(
            stdout="bash\nstats\n", returncode=0
        )
        windows = self.tmux.list_windows("session1")

        self.mock_runner.run.assert_called_with(
            ["tmux", "list-windows", "-t", "session1", "-F", "#{window_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(windows, ["bash", "stats"])

    def test_has_window(self):
        self.mock_runner.run.return_value = MagicMock(
            stdout="bash\nstats\n", returncode=0
        )
        self.assertTrue(self.tmux.has_window("session1", "stats"))
        self.assertFalse(self.tmux.has_window("session1", "other"))

    def test_new_window(self):
        self.mock_runner.run.return_value = MagicMock(returncode=0)
        self.tmux.new_window("session1", "stats", "ls")

        self.mock_runner.run.assert_called_with(
            ["tmux", "new-window", "-t", "session1", "-n", "stats", "-d", "ls"],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_send_keys(self):
        self.mock_runner.run.return_value = MagicMock(returncode=0)
        self.tmux.send_keys("session1:stats", "Escape")

        self.mock_runner.run.assert_called_with(
            ["tmux", "send-keys", "-t", "session1:stats", "Escape"],
            check=False,
        )

    def test_capture_pane(self):
        self.mock_runner.run.return_value = MagicMock(
            stdout="some output", returncode=0
        )
        output = self.tmux.capture_pane("session1:stats")

        self.mock_runner.run.assert_called_with(
            ["tmux", "capture-pane", "-p", "-t", "session1:stats"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(output, "some output")


if __name__ == "__main__":
    unittest.main()
