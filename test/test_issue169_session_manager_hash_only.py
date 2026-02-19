import json
from unittest.mock import patch
import pytest
from copium_loop.session_manager import SessionManager

@pytest.fixture
def temp_session_dir(tmp_path):
    """Fixture to provide a temporary directory for session files."""
    with patch("copium_loop.session_manager.Path.home") as mock_home:
        mock_home.return_value = tmp_path
        yield tmp_path / ".copium" / "sessions"

@pytest.mark.usefixtures("temp_session_dir")
def test_get_jules_session_no_backward_compatibility():
    """Verify that get_jules_session ignores old string-based sessions."""
    manager = SessionManager("test_session")
    
    # Manually inject old-style state into engine_state
    manager.update_engine_state("jules", "node1", "old_session_id")
    
    # Should return None because it's a string, not a dict with hash
    assert manager.get_jules_session("node1") is None

@pytest.mark.usefixtures("temp_session_dir")
def test_get_all_jules_sessions_no_backward_compatibility(temp_session_dir):
    """Verify that get_all_jules_sessions ignores old sessions from disk."""
    session_id = "test_old_session"
    state_file = temp_session_dir / f"{session_id}.json"
    temp_session_dir.mkdir(parents=True, exist_ok=True)
    
    # Create old-style session file on disk
    old_data = {
        "session_id": session_id,
        "jules_sessions": {"node_old": "old_id_1"},
        "engine_state": {
            "jules": {
                "node_str": "old_id_2",
                "node_new": {"session_id": "new_id", "prompt_hash": "abc"}
            }
        },
        "metadata": {}
    }
    with open(state_file, "w") as f:
        json.dump(old_data, f)
        
    manager = SessionManager(session_id)
    sessions = manager.get_all_jules_sessions()
    
    # Should ONLY contain node_new
    assert sessions == {"node_new": "new_id"}

@pytest.mark.usefixtures("temp_session_dir")
def test_get_engine_state_no_backward_compatibility(temp_session_dir):
    """Verify that get_engine_state ignores jules_sessions field from disk."""
    session_id = "test_old_session_2"
    state_file = temp_session_dir / f"{session_id}.json"
    temp_session_dir.mkdir(parents=True, exist_ok=True)

    old_data = {
        "session_id": session_id,
        "jules_sessions": {"node1": "old_id"},
        "engine_state": {},
        "metadata": {}
    }
    with open(state_file, "w") as f:
        json.dump(old_data, f)

    manager = SessionManager(session_id)
    # Should return None because we removed backward compatibility for jules_sessions
    assert manager.get_engine_state("jules", "node1") is None
