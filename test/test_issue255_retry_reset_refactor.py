from unittest.mock import patch

import pytest

from copium_loop.session_manager import SessionManager


@pytest.fixture
def temp_session_dir(tmp_path):
    """Fixture to provide a temporary directory for session files."""
    # Patch the state_dir in SessionManager to use tmp_path
    with patch("copium_loop.session_manager.Path.home") as mock_home:
        mock_home.return_value = tmp_path
        yield tmp_path / ".copium" / "sessions"


@pytest.mark.usefixtures("temp_session_dir")
def test_get_agent_state_reset_retries():
    """
    Test that get_agent_state(reset_retries=True) resets retry_count to 0.
    """
    session_id = "test-session-retry-reset"
    sm = SessionManager(session_id)

    # Set initial state with retry_count > 0
    initial_state = {
        "prompt": "Fix something",
        "retry_count": 5,
        "engine_name": "gemini",
    }
    sm.update_agent_state(initial_state)

    # Verify it's stored correctly
    assert sm.get_agent_state()["retry_count"] == 5

    # Call with reset_retries=True
    # This should fail initially because the parameter doesn't exist yet
    resumed_state = sm.get_agent_state(reset_retries=True)

    assert resumed_state["retry_count"] == 0
    # The original state in SessionManager should also be updated (or not, depending on implementation)
    # Usually we want the resumed state to be what's used, and the next save will update it on disk.
    assert sm.get_agent_state()["retry_count"] == 0


@pytest.mark.usefixtures("temp_session_dir")
def test_get_agent_state_no_reset_by_default():
    """
    Test that get_agent_state() does NOT reset retry_count by default.
    """
    session_id = "test-session-no-reset"
    sm = SessionManager(session_id)

    initial_state = {"retry_count": 5}
    sm.update_agent_state(initial_state)

    assert sm.get_agent_state()["retry_count"] == 5
