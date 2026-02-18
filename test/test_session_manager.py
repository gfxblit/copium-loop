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
    manager.update_jules_session("node1", "session_123")
    manager.update_metadata("key1", "value1")

    # Verify data in memory
    assert manager.get_jules_session("node1") == "session_123"
    assert manager.get_metadata("key1") == "value1"

    # Verify data on disk
    assert manager.state_file.exists()
    with open(manager.state_file) as f:
        data = json.load(f)
        assert data["session_id"] == "test_session"
        assert data["engine_state"]["jules"]["node1"] == "session_123"
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
    manager.update_jules_session("node1", "session_123")

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
    manager.update_jules_session("node1", "new_session")
    assert manager.get_jules_session("node1") == "new_session"

    with open(manager.state_file) as f:
        data = json.load(f)
        assert data["engine_state"]["jules"]["node1"] == "new_session"
