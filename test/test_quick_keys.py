import os
import subprocess
import unittest
from unittest.mock import patch

from src.copium_loop.ui.column import SessionColumn
from src.copium_loop.ui.dashboard import Dashboard
from src.copium_loop.ui.tmux import extract_tmux_session, switch_to_tmux_session


class TestQuickKeys(unittest.TestCase):
    def test_extract_tmux_session_simple(self):
        """Test simple session names."""
        self.assertEqual(extract_tmux_session("my-session"), "my-session")
        self.assertEqual(extract_tmux_session("dev"), "dev")

    def test_extract_tmux_session_with_pane(self):
        """Test session names with pane suffix (old format)."""
        self.assertEqual(extract_tmux_session("my-session_1"), "my-session")
        self.assertEqual(extract_tmux_session("project_%1"), "project")

    def test_extract_tmux_session_numeric_suffix(self):
        """Test session names that naturally have underscores but are not panes."""
        # If the suffix is NOT just digits or %digits, it should be part of the name
        self.assertEqual(extract_tmux_session("my_session_name"), "my_session_name")

    def test_extract_tmux_session_session_prefix(self):
        """Test that session_ prefix is handled correctly."""
        # The requirement says 'session_123456789' should be identified.
        # Assuming if it looks like a generated session ID but corresponds to a tmux session?
        # Or maybe the requirement means we SHOULD treat 'session_123456789' as a valid tmux session name if it exists?
        # The current code returns None for session_*.
        # Let's assume the requirement implies we should return it.
        self.assertEqual(extract_tmux_session("session_123456789"), "session_123456789")

    @patch("src.copium_loop.ui.tmux.subprocess.run")
    @patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default"})
    def test_switch_to_tmux_session_success(self, mock_run):
        """Test successful switch."""
        switch_to_tmux_session("target")
        mock_run.assert_called_with(
            ["tmux", "switch-client", "-t", "--", "target"],
            check=True,
            capture_output=True,
            text=True
        )

    @patch("src.copium_loop.ui.tmux.subprocess.run")
    @patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default"})
    def test_switch_to_tmux_session_failure(self, mock_run):
        """Test switch failure (should be silent)."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
        # Should not raise exception
        switch_to_tmux_session("non-existent")

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.copium_loop.ui.tmux.subprocess.run")
    def test_switch_to_tmux_session_no_tmux(self, mock_run):
        """Test switch when not in tmux."""
        switch_to_tmux_session("target")
        mock_run.assert_not_called()

class TestDashboardQuickKeys(unittest.TestCase):
    def setUp(self):
        self.dashboard = Dashboard()
        # Mock sessions
        self.s1 = SessionColumn("session1")
        self.s2 = SessionColumn("session2")
        self.s3 = SessionColumn("session3")
        self.s4 = SessionColumn("session4")

        # Determine sort order helpers
        # Dashboard sorts by (running, activated_at, session_id).
        # Let's make them all running for simplicity.
        self.s1.workflow_status = "running"
        self.s1.activated_at = 100

        self.s2.workflow_status = "running"
        self.s2.activated_at = 200

        self.s3.workflow_status = "running"
        self.s3.activated_at = 300

        self.s4.workflow_status = "running"
        self.s4.activated_at = 400

        self.dashboard.sessions = {
            "s1": self.s1,
            "s2": self.s2,
            "s3": self.s3,
            "s4": self.s4
        }
        self.dashboard.sessions_per_page = 3

    @patch("src.copium_loop.ui.dashboard.InputReader")
    @patch("src.copium_loop.ui.dashboard.Live")
    @patch("src.copium_loop.ui.dashboard.switch_to_tmux_session")
    @patch("src.copium_loop.ui.dashboard.extract_tmux_session")
    @patch("src.copium_loop.ui.dashboard.termios")
    @patch("src.copium_loop.ui.dashboard.tty")
    @patch("src.copium_loop.ui.dashboard.sys.stdin")
    def test_quick_key_page_1(self, mock_stdin, _mock_tty, _mock_termios, mock_extract, mock_switch, _mock_live, mock_input_reader):
        """Test pressing '2' on page 1."""
        # Setup mocks
        mock_reader_instance = mock_input_reader.return_value
        # Sequence: '2', then 'q' to quit
        mock_reader_instance.get_key.side_effect = ["2", "q"]

        mock_extract.side_effect = lambda x: x # Identity for simplicity

        # Mock termios/tty calls
        mock_stdin.fileno.return_value = 1

        # Prevent update_from_logs from overwriting our sessions
        with patch.object(self.dashboard, 'update_from_logs'):
             self.dashboard.run_monitor()

        # On page 1 (idx 0), sessions are s1, s2, s3 (sorted by time)
        # s1 is oldest (100), s2 (200), s3 (300).
        # key '2' corresponds to 2nd session -> s2.

        mock_extract.assert_called_with("session2") # session_id of s2
        mock_switch.assert_called_with("session2")

    @patch("src.copium_loop.ui.dashboard.InputReader")
    @patch("src.copium_loop.ui.dashboard.Live")
    @patch("src.copium_loop.ui.dashboard.switch_to_tmux_session")
    @patch("src.copium_loop.ui.dashboard.extract_tmux_session")
    @patch("src.copium_loop.ui.dashboard.termios")
    @patch("src.copium_loop.ui.dashboard.tty")
    @patch("src.copium_loop.ui.dashboard.sys.stdin")
    def test_quick_key_page_2(self, mock_stdin, _mock_tty, _mock_termios, mock_extract, mock_switch, _mock_live, mock_input_reader):
        """Test pressing '1' on page 2."""
        # Setup mocks
        mock_reader_instance = mock_input_reader.return_value
        # Sequence: Right Arrow (next page), '1', 'q'
        mock_reader_instance.get_key.side_effect = ["\x1b[C", "1", "q"]

        mock_extract.side_effect = lambda x: x

        mock_stdin.fileno.return_value = 1

        # Prevent update_from_logs from overwriting our sessions
        with patch.object(self.dashboard, 'update_from_logs'):
            self.dashboard.run_monitor()

        # On page 2 (idx 1), session is s4.
        # key '1' corresponds to 1st session on page -> s4.

        mock_extract.assert_called_with("session4")
        mock_switch.assert_called_with("session4")

    @patch("src.copium_loop.ui.dashboard.InputReader")
    @patch("src.copium_loop.ui.dashboard.Live")
    @patch("src.copium_loop.ui.dashboard.switch_to_tmux_session")
    @patch("src.copium_loop.ui.dashboard.termios")
    @patch("src.copium_loop.ui.dashboard.tty")
    @patch("src.copium_loop.ui.dashboard.sys.stdin")
    def test_quick_key_invalid(self, mock_stdin, _mock_tty, _mock_termios, mock_switch, _mock_live, mock_input_reader):
        """Test pressing '9' when only 3 sessions on page."""
        mock_reader_instance = mock_input_reader.return_value
        mock_reader_instance.get_key.side_effect = ["9", "q"]

        mock_stdin.fileno.return_value = 1

        # Prevent update_from_logs from overwriting our sessions
        with patch.object(self.dashboard, 'update_from_logs'):
            self.dashboard.run_monitor()

        mock_switch.assert_not_called()
