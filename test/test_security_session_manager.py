import os
import pytest
from pathlib import Path
from copium_loop.session_manager import SessionManager

def test_session_manager_path_traversal():
    """
    Verifies that SessionManager prevents path traversal.
    """
    # Create a session ID with path traversal characters
    malicious_session_id = "../../evil_session"

    # Initialize SessionManager with the malicious session ID should raise ValueError
    with pytest.raises(ValueError, match="Invalid session ID"):
        SessionManager(malicious_session_id)

    # Also test valid session ID works
    valid_session_id = "valid-session-id"
    manager = SessionManager(valid_session_id)
    expected_base_dir = Path.home() / ".copium" / "sessions"
    actual_path = manager.state_file.resolve()
    assert str(actual_path).startswith(str(expected_base_dir.resolve()))
    assert actual_path.name == f"{valid_session_id}.json"

def test_session_manager_sanitize_separators():
    """
    Verifies that SessionManager sanitizes path separators.
    """
    # Session ID with separators (common for owner/repo pattern)
    session_id = "owner/repo"
    manager = SessionManager(session_id)

    # Check that it resolves correctly within the sessions directory
    expected_base_dir = Path.home() / ".copium" / "sessions"
    actual_path = manager.state_file.resolve()

    assert str(actual_path).startswith(str(expected_base_dir.resolve()))
    # Should be flattened
    assert actual_path.name == "owner_repo.json"
