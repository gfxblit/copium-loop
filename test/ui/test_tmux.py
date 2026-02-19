import subprocess
from unittest.mock import MagicMock, patch

from copium_loop.ui.tmux import extract_tmux_session, switch_to_tmux_session


def test_extract_tmux_session_basic():
    """Test that extract_tmux_session correctly parses session IDs."""
    assert extract_tmux_session("my_session") == "my_session"
    assert extract_tmux_session("my_session_0") == "my_session_0"
    assert extract_tmux_session("my_session_%1") == "%1"
    assert extract_tmux_session("session_12345678") == "session_12345678"


def test_extract_tmux_session_new_format():
    """Test that extract_tmux_session handles the new session-only format."""
    session_id = "my-awesome-session"
    assert extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_old_format_with_percent():
    """Test that extract_tmux_session still handles the old format with % pane ID."""
    session_id = "my-awesome-session_%179"
    assert extract_tmux_session(session_id) == "%179"


def test_extract_tmux_session_old_format_without_percent():
    """Test that extract_tmux_session no longer handles the old format with numeric-only pane ID to avoid collisions."""
    session_id = "my-awesome-session_123"
    assert extract_tmux_session(session_id) == "my-awesome-session_123"


def test_extract_tmux_session_not_tmux():
    """Test that session_timestamp is treated as a valid session name (per issue #30)."""
    session_id = "session_1234567890"
    assert extract_tmux_session(session_id) == "session_1234567890"


def test_extract_tmux_session_collision():
    """Test that a session named 'project_1' is preserved and not stripped to 'project'."""
    session_name = "project_1"
    extracted = extract_tmux_session(session_name)
    # We expect it to be preserved because it's a valid session name
    assert extracted == "project_1"


def test_extract_tmux_session_name_with_underscore():
    """Test that extract_tmux_session handles session names that contain underscores."""
    # If the session name itself has an underscore and we use the new format
    session_id = "my_project_v2"
    # It should return the whole thing because it doesn't end in a pane-like suffix
    assert extract_tmux_session(session_id) == "my_project_v2"


def test_extract_tmux_session_old_format_with_underscore_in_name():
    """Test old format where the session name itself contains an underscore."""
    session_id = "my_project_v2_%5"
    assert extract_tmux_session(session_id) == "%5"


def test_switch_to_tmux_session_success():
    """Test switching tmux sessions (mocked)."""
    with (
        patch("subprocess.run") as mock_run,
        patch.dict("os.environ", {"TMUX": "/tmp/tmux-1234/default,1234,0"}),
    ):
        mock_run.return_value.returncode = 0
        switch_to_tmux_session("target_session")
        # Should be called once because the first attempt (target_session) succeeds
        mock_run.assert_called_with(
            ["tmux", "switch-client", "-t", "target_session"],
            check=True,
            capture_output=True,
            text=True,
        )


def test_switch_to_tmux_session_pane_id():
    """Test switching to a pane ID extracted from the session name."""
    with (
        patch("subprocess.run") as mock_run,
        patch.dict("os.environ", {"TMUX": "/tmp/tmux-1234/default,1234,0"}),
    ):
        mock_run.return_value.returncode = 0
        switch_to_tmux_session("my_session_%10")

        # It should identify %10 as the target
        mock_run.assert_called_once_with(
            ["tmux", "switch-client", "-t", "%10"],
            check=True,
            capture_output=True,
            text=True,
        )


def test_switch_to_tmux_session_no_fallback():
    """Test that switch_to_tmux_session does NOT fallback (per new architecture)."""
    with (
        patch("subprocess.run") as mock_run,
        patch.dict("os.environ", {"TMUX": "/tmp/tmux-1234/default,1234,0"}),
    ):
        # First call fails
        mock_run.side_effect = subprocess.CalledProcessError(1, "tmux")

        switch_to_tmux_session("target_session")

        # Should only be called once with the extracted target
        assert mock_run.call_count == 1
        mock_run.assert_called_with(
            ["tmux", "switch-client", "-t", "target_session"],
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
