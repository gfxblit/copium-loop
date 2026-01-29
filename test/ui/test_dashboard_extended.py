import json
from unittest.mock import MagicMock, patch

from copium_loop.ui.dashboard import Dashboard


def test_dashboard_update_from_logs_invalid_timestamp(tmp_path):
    """Test that invalid timestamps in logs are handled gracefully."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    log_file = tmp_path / "session1.jsonl"
    events = [
        {
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "running",
            "timestamp": "invalid-timestamp",
        }
    ]
    with open(log_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    # This should not raise an error
    dash.update_from_logs()

    assert "session1" in dash.sessions
    assert dash.sessions["session1"].created_at == 0


def test_dashboard_update_from_logs_invalid_json(tmp_path):
    """Test that invalid JSON lines in logs are ignored."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    log_file = tmp_path / "session1.jsonl"
    with open(log_file, "w") as f:
        f.write("invalid json\n")
        f.write(
            json.dumps(
                {
                    "node": "workflow",
                    "event_type": "workflow_status",
                    "data": "running",
                    "timestamp": "2026-01-28T10:00:00",
                }
            )
            + "\n"
        )

    dash.update_from_logs()

    assert "session1" in dash.sessions
    assert dash.sessions["session1"].workflow_status == "running"


def test_dashboard_run_monitor_exit_q(tmp_path):
    """Test that run_monitor exits when 'q' is pressed."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    with (
        patch("copium_loop.ui.dashboard.Live") as mock_live,
        patch("copium_loop.ui.dashboard.InputReader") as mock_input,
        patch("copium_loop.ui.dashboard.termios") as mock_termios,
        patch("copium_loop.ui.dashboard.tty") as mock_tty,
        patch("copium_loop.ui.dashboard.time.sleep"),
        patch("copium_loop.ui.dashboard.sys.stdin.fileno", return_value=0),
    ):
        mock_input_instance = mock_input.return_value
        # First call returns 'q'
        mock_input_instance.get_key.return_value = "q"

        dash.run_monitor()

        assert mock_live.called
        assert mock_termios.tcgetattr.called
        assert mock_termios.tcsetattr.called
        assert mock_tty.setcbreak.called


def test_dashboard_run_monitor_navigation(tmp_path):
    """Test that run_monitor handles navigation keys."""
    dash = Dashboard()
    dash.log_dir = tmp_path
    dash.sessions_per_page = 1

    # Add two sessions
    dash.sessions = {
        "s1": MagicMock(session_id="s1", workflow_status="running", activated_at=1),
        "s2": MagicMock(session_id="s2", workflow_status="running", activated_at=2),
    }

    with (
        patch("copium_loop.ui.dashboard.Live"),
        patch("copium_loop.ui.dashboard.InputReader") as mock_input,
        patch("copium_loop.ui.dashboard.termios"),
        patch("copium_loop.ui.dashboard.tty"),
        patch("copium_loop.ui.dashboard.time.sleep"),
        patch("copium_loop.ui.dashboard.sys.stdin.fileno", return_value=0),
        patch.object(Dashboard, "update_from_logs"),
    ):
        mock_input_instance = mock_input.return_value
        # Sequence of keys: Tab, then q
        mock_input_instance.get_key.side_effect = ["\t", "q"]

        dash.run_monitor()

        # current_page should have changed to 1 and then we exited
        assert dash.current_page == 1


def test_dashboard_run_monitor_back_navigation(tmp_path):
    """Test that run_monitor handles back navigation keys."""
    dash = Dashboard()
    dash.log_dir = tmp_path
    dash.sessions_per_page = 1

    # Add two sessions
    dash.sessions = {
        "s1": MagicMock(session_id="s1", workflow_status="running", activated_at=1),
        "s2": MagicMock(session_id="s2", workflow_status="running", activated_at=2),
    }
    # dash.current_page will be reset to 0 by run_monitor

    with (
        patch("copium_loop.ui.dashboard.Live"),
        patch("copium_loop.ui.dashboard.InputReader") as mock_input,
        patch("copium_loop.ui.dashboard.termios"),
        patch("copium_loop.ui.dashboard.tty"),
        patch("copium_loop.ui.dashboard.time.sleep"),
        patch("copium_loop.ui.dashboard.sys.stdin.fileno", return_value=0),
        patch.object(Dashboard, "update_from_logs"),
    ):
        mock_input_instance = mock_input.return_value
        # Sequence of keys: Shift+Tab, then q
        # (0 - 1) % 2 = 1
        mock_input_instance.get_key.side_effect = ["\x1b[Z", "q"]

        dash.run_monitor()

        # current_page should have changed to 1 and then we exited
        assert dash.current_page == 1


def test_dashboard_run_monitor_refresh(tmp_path):
    """Test that run_monitor handles 'r' key for manual refresh."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    with (
        patch("copium_loop.ui.dashboard.Live"),
        patch("copium_loop.ui.dashboard.InputReader") as mock_input,
        patch("copium_loop.ui.dashboard.termios"),
        patch("copium_loop.ui.dashboard.tty"),
        patch("copium_loop.ui.dashboard.time.sleep"),
        patch("copium_loop.ui.dashboard.sys.stdin.fileno", return_value=0),
        patch.object(Dashboard, "update_from_logs") as mock_update,
    ):
        mock_input_instance = mock_input.return_value
        # Sequence of keys: 'r', then q
        mock_input_instance.get_key.side_effect = ["r", "q"]

        dash.run_monitor()

        # update_from_logs should be called at least 2 times (one at start of loop, one for 'r')
        assert mock_update.call_count >= 2


def test_dashboard_run_monitor_switch_session(tmp_path):
    """Test that run_monitor handles session switching with number keys."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    s1 = MagicMock(session_id="session_1")
    dash.sessions = {"session_1": s1}
    # Mock get_sorted_sessions to return our mock session
    dash.get_sorted_sessions = MagicMock(return_value=[s1])

    with (
        patch("copium_loop.ui.dashboard.Live"),
        patch("copium_loop.ui.dashboard.InputReader") as mock_input,
        patch("copium_loop.ui.dashboard.termios"),
        patch("copium_loop.ui.dashboard.tty"),
        patch("copium_loop.ui.dashboard.time.sleep"),
        patch("copium_loop.ui.dashboard.sys.stdin.fileno", return_value=0),
        patch("copium_loop.ui.dashboard.extract_tmux_session") as mock_extract,
        patch("copium_loop.ui.dashboard.switch_to_tmux_session") as mock_switch,
        patch.object(Dashboard, "update_from_logs"),
    ):
        mock_input_instance = mock_input.return_value
        # Sequence of keys: '1', then q
        mock_input_instance.get_key.side_effect = ["1", "q"]
        mock_extract.return_value = "tmux_s1"

        dash.run_monitor()

        mock_extract.assert_called_with("session_1")
        mock_switch.assert_called_with("tmux_s1")


def test_dashboard_update_from_logs_workflow_invalid_timestamp(tmp_path):
    """Test that invalid timestamps in workflow status events are handled gracefully."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    log_file = tmp_path / "session1.jsonl"
    events = [
        {
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "success",
            "timestamp": "invalid-timestamp",
        }
    ]
    with open(log_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    dash.update_from_logs()

    assert "session1" in dash.sessions
    assert dash.sessions["session1"].workflow_status == "success"
    # It will be set to time.time() by the setter because the override failed
    assert dash.sessions["session1"].completed_at > 0
