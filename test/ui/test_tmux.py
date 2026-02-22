import os
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
    assert extracted == "project_1"


def test_extract_tmux_session_name_with_underscore():
    """Test that extract_tmux_session handles session names that contain underscores."""
    session_id = "my_project_v2"
    assert extract_tmux_session(session_id) == "my_project_v2"


def test_extract_tmux_session_old_format_with_underscore_in_name():
    """Test old format where the session name itself contains an underscore."""
    session_id = "my_project_v2_%5"
    assert extract_tmux_session(session_id) == "%5"


def test_extract_tmux_session_with_path_prefix():
    """Test that extract_tmux_session correctly strips repo prefixes."""
    assert extract_tmux_session("myrepo/my_session") == "my_session"
    assert extract_tmux_session("myrepo/my_session_0") == "my_session_0"
    assert extract_tmux_session("myrepo/my_session_%1") == "%1"
    assert extract_tmux_session("github.com/user/repo/session_1234") == "session_1234"


def test_switch_to_tmux_session_success():
    """Test switching tmux sessions (mocked) with socket path."""
    with (
        patch("copium_loop.ui.tmux.subprocess.run") as mock_run,
        patch.dict("os.environ", {"TMUX": "/tmp/tmux-1234/default,1234,0"}),
    ):
        mock_run.return_value.returncode = 0
        switch_to_tmux_session("target_session")
        mock_run.assert_called_with(
            ["tmux", "-S", "/tmp/tmux-1234/default", "switch-client", "-t", "target_session"],
            check=True,
            capture_output=True,
            text=True,
        )


def test_switch_to_tmux_session_fallback():
    """Test switching tmux sessions with fallback (mocked) with socket path."""
    with (
        patch("copium_loop.ui.tmux.subprocess.run") as mock_run,
        patch.dict("os.environ", {"TMUX": "/tmp/tmux-1234/default,1234,0"}),
    ):
        mock_result = MagicMock()
        mock_result.returncode = 0

        # First call fails, second succeeds
        mock_run.side_effect = [subprocess.CalledProcessError(1, "tmux"), mock_result]

        switch_to_tmux_session("target_session")

        assert mock_run.call_count == 2
        mock_run.assert_any_call(
            ["tmux", "-S", "/tmp/tmux-1234/default", "switch-client", "-t", "target_session"],
            check=True,
            capture_output=True,
            text=True,
        )
        mock_run.assert_any_call(
            ["tmux", "-S", "/tmp/tmux-1234/default", "switch-client", "-t", "target"],
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


def test_switch_to_tmux_session_no_tmux_env():
    """Test that switch_to_tmux_session returns early if TMUX env is not set."""
    with (
        patch.dict(os.environ, {}, clear=True),
        patch("subprocess.run") as mock_run,
    ):
        switch_to_tmux_session("my-session")
        mock_run.assert_not_called()


def test_switch_to_tmux_session_called_process_error():
    """Test that switch_to_tmux_session handles subprocess.CalledProcessError."""
    with (
        patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,123,0"}),
        patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["tmux"])),
    ):
        # Should not raise an exception
        switch_to_tmux_session("non-existent-session")


def test_switch_to_tmux_session_unexpected_error_extended(capsys):
    """Test that switch_to_tmux_session handles unexpected exceptions."""
    with (
        patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,123,0"}),
        patch("subprocess.run", side_effect=Exception("kaboom")),
    ):
        switch_to_tmux_session("my-session")
        captured = capsys.readouterr()
        assert (
            "Unexpected error switching to tmux session 'my-session': kaboom"
            in captured.err
        )
