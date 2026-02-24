import json
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


def test_session_manager_initialization(temp_session_dir):
    """Test that SessionManager initializes correctly and creates the directory."""
    manager = SessionManager("test_session")
    assert manager.session_id == "test_session"
    assert manager.state_dir == temp_session_dir
    assert manager.state_dir.exists()
    assert manager.state_file == temp_session_dir / "test_session.json"


@pytest.mark.usefixtures("temp_session_dir")
def test_save_and_load_session():
    """Test saving and loading session data."""
    manager = SessionManager("test_session")
    manager.update_jules_session("node1", "session_123", prompt_hash="test_hash")
    manager.update_metadata("key1", "value1")

    # Verify data in memory
    assert manager.get_jules_session("node1") == "session_123"
    assert manager.get_metadata("key1") == "value1"

    # Verify data on disk
    assert manager.state_file.exists()
    with open(manager.state_file) as f:
        data = json.load(f)
        assert data["session_id"] == "test_session"
        assert data["engine_state"]["jules"]["node1"]["session_id"] == "session_123"
        assert data["metadata"]["key1"] == "value1"

    # Test loading from disk
    new_manager = SessionManager("test_session")
    assert new_manager.get_jules_session("node1") == "session_123"
    assert new_manager.get_metadata("key1") == "value1"


@pytest.mark.usefixtures("temp_session_dir")
def test_atomic_write():
    """Test that writes are atomic (using a mock to simulate failure during write if possible,
    or just ensuring the file is valid)."""
    manager = SessionManager("test_session")
    manager.update_jules_session("node1", "session_123", prompt_hash="test_hash")

    # Check that temp file is cleaned up
    # This is hard to test directly without mocking NamedTemporaryFile or os.replace
    # But we can check that the final file is valid JSON
    with open(manager.state_file) as f:
        data = json.load(f)
    assert data is not None


def test_corrupted_session_file(temp_session_dir):
    """Test that SessionManager handles corrupted session files gracefully."""
    # Create a corrupted file
    session_dir = temp_session_dir
    session_dir.mkdir(parents=True, exist_ok=True)
    with open(session_dir / "corrupted_session.json", "w") as f:
        f.write("{invalid_json")

    manager = SessionManager("corrupted_session")
    # Should initialize with empty state despite corruption
    assert manager.get_jules_session("node1") is None

    # Should be able to save new data overwriting corruption
    manager.update_jules_session("node1", "new_session", prompt_hash="new_hash")
    assert manager.get_jules_session("node1") == "new_session"

    with open(manager.state_file) as f:
        data = json.load(f)
        assert data["engine_state"]["jules"]["node1"]["session_id"] == "new_session"


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
                "node_new": {"session_id": "new_id", "prompt_hash": "abc"},
            }
        },
        "metadata": {},
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
        "metadata": {},
    }
    with open(state_file, "w") as f:
        json.dump(old_data, f)

    manager = SessionManager(session_id)
    # Should return None because we removed backward compatibility for jules_sessions
    assert manager.get_engine_state("jules", "node1") is None


def test_session_manager_engine_state(tmp_path):
    session_id = "test-session-refactor"
    sm = SessionManager(session_id)
    # Redirect to tmp_path
    sm.state_dir = tmp_path
    sm.state_file = tmp_path / f"{session_id}.json"

    # Test update_engine_state
    sm.update_engine_state("jules", "node1", {"session_id": "sess-123"})

    # Test get_engine_state
    state = sm.get_engine_state("jules", "node1")
    assert state == {"session_id": "sess-123"}

    # Test persistence
    sm._save()

    sm2 = SessionManager(session_id)
    sm2.state_dir = tmp_path
    sm2.state_file = tmp_path / f"{session_id}.json"
    sm2._load()

    assert sm2.get_engine_state("jules", "node1") == {"session_id": "sess-123"}


@pytest.mark.usefixtures("temp_session_dir")
def test_session_manager_agent_state():
    """Test updating and retrieving agent state."""
    manager = SessionManager("test_session")
    state = {"prompt": "test prompt", "retry_count": 5}
    manager.update_agent_state(state)

    assert manager.get_agent_state() == state


@pytest.mark.usefixtures("temp_session_dir")
def test_session_manager_get_resumed_state():
    """Test that get_resumed_state resets retry_count to 0."""
    manager = SessionManager("test_session")
    state = {"prompt": "test prompt", "retry_count": 5}
    manager.update_agent_state(state)

    resumed_state = manager.get_resumed_state()
    assert resumed_state["retry_count"] == 0
    assert manager.get_agent_state()["retry_count"] == 0
