from unittest.mock import patch

from copium_loop.ui import Dashboard, switch_to_tmux_session


def test_dashboard_update_from_logs_error_handling(tmp_path, capsys):
    """Test that Dashboard.update_from_logs reports errors to stderr."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    # Create a log file that we can't open
    log_file = tmp_path / "error_session.jsonl"
    log_file.write_text("{}")

    # Use patch to make 'open' fail for this specific file
    original_open = open

    def mock_open(file, *args, **kwargs):
        if str(file) == str(log_file):
            raise Exception("Simulated file error")
        return original_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=mock_open):
        dash.update_from_logs()

    captured = capsys.readouterr()
    assert f"Error processing log file {log_file}: Simulated file error" in captured.err


def test_switch_to_tmux_session_error_handling(capsys):
    """Test that switch_to_tmux_session reports unexpected errors to stderr."""
    with (
        patch("os.environ", {"TMUX": "/tmp/tmux-1234/default,1234,0"}),
        patch("subprocess.run", side_effect=Exception("Simulated tmux error")),
    ):
        switch_to_tmux_session("target_session")

    captured = capsys.readouterr()
    assert (
        "Unexpected error switching to tmux session 'target_session': Simulated tmux error"
        in captured.err
    )
