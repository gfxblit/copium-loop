from unittest.mock import patch

from copium_loop.ui.tmux import extract_tmux_session, switch_to_tmux_session


def test_extract_tmux_session_basic():
    """Test that extract_tmux_session correctly parses session IDs."""
    assert extract_tmux_session("my_session") == "my_session"
    assert extract_tmux_session("my_session_0") == "my_session"
    assert extract_tmux_session("my_session_%1") == "my_session"
    assert extract_tmux_session("session_12345678") is None


def test_extract_tmux_session_new_format():
    """Test that extract_tmux_session handles the new session-only format."""
    session_id = "my-awesome-session"
    assert extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_old_format_with_percent():
    """Test that extract_tmux_session still handles the old format with % pane ID."""
    session_id = "my-awesome-session_%179"
    assert extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_old_format_without_percent():
    """Test that extract_tmux_session handles the old format with numeric pane ID."""
    session_id = "my-awesome-session_123"
    assert extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_not_tmux():
    """Test that extract_tmux_session returns None for non-tmux session IDs."""
    session_id = "session_1234567890"
    assert extract_tmux_session(session_id) is None


def test_extract_tmux_session_name_with_underscore():
    """Test that extract_tmux_session handles session names that contain underscores."""
    # If the session name itself has an underscore and we use the new format
    session_id = "my_project_v2"
    # It should return the whole thing because it doesn't end in a pane-like suffix
    assert extract_tmux_session(session_id) == "my_project_v2"


def test_extract_tmux_session_old_format_with_underscore_in_name():
    """Test old format where the session name itself contains an underscore."""
    session_id = "my_project_v2_%5"
    assert extract_tmux_session(session_id) == "my_project_v2"


def test_switch_to_tmux_session_success():
    """Test switching tmux sessions (mocked)."""
    with (
        patch("subprocess.run") as mock_run,
        patch.dict("os.environ", {"TMUX": "/tmp/tmux-1234/default,1234,0"}),
    ):
        switch_to_tmux_session("target_session")
        mock_run.assert_called_once_with(
            ["tmux", "switch-client", "-t", "--", "target_session"],
            check=True,
            capture_output=True,
            text=True,
        )


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
