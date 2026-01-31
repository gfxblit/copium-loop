import os
import unittest
from unittest.mock import patch

from src.copium_loop.ui.column import SessionColumn
from src.copium_loop.ui.dashboard import Dashboard
from src.copium_loop.ui.tmux import extract_tmux_session


class TestIssue30Repro(unittest.TestCase):
    def setUp(self):
        self.dashboard = Dashboard()
        # Create some dummy sessions
        self.s1 = SessionColumn("session-1")
        self.s1.workflow_status = "running"
        self.s1.activated_at = 100

        self.s2 = SessionColumn("session-2")
        self.s2.workflow_status = "running"
        self.s2.activated_at = 200

        self.dashboard.sessions = {
            "session-1": self.s1,
            "session-2": self.s2
        }

    def test_extract_tmux_session_collision(self):
        """Test that a session named 'project_1' is preserved and not stripped to 'project'."""
        session_name = "project_1"
        extracted = extract_tmux_session(session_name)
        # We expect it to be preserved because it's a valid session name
        self.assertEqual(extracted, "project_1")

    @patch("src.copium_loop.ui.dashboard.switch_to_tmux_session")
    @patch("src.copium_loop.ui.dashboard.InputReader")
    @patch("src.copium_loop.ui.dashboard.Live")
    @patch("src.copium_loop.ui.dashboard.termios")
    @patch("src.copium_loop.ui.dashboard.tty")
    @patch("src.copium_loop.ui.dashboard.sys.stdin")
    def test_key_one_switches_session(self, mock_stdin, _mock_tty, _mock_termios, _mock_live, mock_input_reader_cls, mock_switch):
        # Setup mocks
        mock_reader = mock_input_reader_cls.return_value
        # Simulate pressing '1' then 'q'
        mock_reader.get_key.side_effect = ["1", "q"]

        mock_stdin.fileno.return_value = 1

        # Run monitor
        with patch.object(self.dashboard, 'update_from_logs'):
            self.dashboard.run_monitor()

        # Verify switch was called for the first session (session-1)
        mock_switch.assert_called_with("session-1")

    @patch("src.copium_loop.ui.dashboard.switch_to_tmux_session")
    @patch("src.copium_loop.ui.dashboard.Live")
    @patch("src.copium_loop.ui.dashboard.termios")
    @patch("src.copium_loop.ui.dashboard.tty")
    def test_key_one_switches_session_real_reader(self, _mock_tty, _mock_termios, _mock_live, mock_switch):
        # Create a pipe to simulate stdin
        r, w = os.pipe()

        # Write '1' (switch) and 'q' (quit)
        os.write(w, b"1q")
        os.close(w)

        # Wrap the read end of the pipe in a file object to replace sys.stdin
        with os.fdopen(r, 'r') as mock_stdin_f, \
             patch("src.copium_loop.input_reader.sys.stdin", mock_stdin_f), \
             patch("src.copium_loop.ui.dashboard.sys.stdin", mock_stdin_f), \
             patch.object(self.dashboard, 'update_from_logs'):
                self.dashboard.run_monitor()

        # Verify switch was called for the first session
        mock_switch.assert_called_with("session-1")
