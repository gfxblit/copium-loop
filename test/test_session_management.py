from unittest.mock import MagicMock, patch

import pytest

from copium_loop import telemetry
from copium_loop.ui import Dashboard


@pytest.fixture(autouse=True)
def reset_telemetry_singleton():
    """Reset the telemetry singleton before each test."""
    telemetry._telemetry_instance = None
    yield
    telemetry._telemetry_instance = None


def test_get_telemetry_uses_tmux_session_name():
    """Test that get_telemetry uses only the tmux session name when available."""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "my-awesome-session\n"

    with patch("subprocess.run", return_value=mock_res):
        t = telemetry.get_telemetry()
        assert t.session_id == "my-awesome-session"


def test_get_telemetry_fallback_to_timestamp():
    """Test that get_telemetry falls back to session_timestamp when tmux is not available."""
    with (
        patch("subprocess.run", side_effect=Exception("no tmux")),
        patch("time.time", return_value=1234567890),
    ):
        t = telemetry.get_telemetry()
        assert t.session_id == "session_1234567890"


def test_extract_tmux_session_new_format():
    """Test that extract_tmux_session handles the new session-only format."""
    dashboard = Dashboard()
    session_id = "my-awesome-session"
    assert dashboard.extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_old_format_with_percent():
    """Test that extract_tmux_session still handles the old format with % pane ID."""
    dashboard = Dashboard()
    session_id = "my-awesome-session_%179"
    assert dashboard.extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_old_format_without_percent():
    """Test that extract_tmux_session handles the old format with numeric pane ID."""
    dashboard = Dashboard()
    session_id = "my-awesome-session_123"
    assert dashboard.extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_not_tmux():
    """Test that extract_tmux_session returns None for non-tmux session IDs."""
    dashboard = Dashboard()
    session_id = "session_1234567890"
    assert dashboard.extract_tmux_session(session_id) is None


def test_extract_tmux_session_name_with_underscore():
    """Test that extract_tmux_session handles session names that contain underscores."""
    dashboard = Dashboard()
    # If the session name itself has an underscore and we use the new format
    session_id = "my_project_v2"
    # It should return the whole thing because it doesn't end in a pane-like suffix
    assert dashboard.extract_tmux_session(session_id) == "my_project_v2"


def test_extract_tmux_session_old_format_with_underscore_in_name():
    """Test old format where the session name itself contains an underscore."""
    dashboard = Dashboard()
    session_id = "my_project_v2_%5"
    assert dashboard.extract_tmux_session(session_id) == "my_project_v2"
