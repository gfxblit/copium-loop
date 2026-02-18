from copium_loop.session_manager import SessionData, SessionManager


def test_session_manager_engine_state(tmp_path):
    session_id = "test-session"
    sm = SessionManager(session_id)
    # Redirect to tmp_path
    sm.state_dir = tmp_path
    sm.state_file = tmp_path / f"{session_id}.json"

    # Test update_engine_state (RED: method won't exist)
    sm.update_engine_state("jules", "node1", {"session_id": "sess-123"})

    # Test get_engine_state (RED: method won't exist)
    state = sm.get_engine_state("jules", "node1")
    assert state == {"session_id": "sess-123"}

    # Test persistence
    sm._save()

    sm2 = SessionManager(session_id)
    sm2.state_dir = tmp_path
    sm2.state_file = tmp_path / f"{session_id}.json"
    sm2._load()

    assert sm2.get_engine_state("jules", "node1") == {"session_id": "sess-123"}


def test_session_manager_migration(tmp_path):
    session_id = "test-migration"

    # Create a session with the OLD format
    sm = SessionManager(session_id)
    sm.state_dir = tmp_path
    sm.state_file = tmp_path / f"{session_id}.json"

    # Inject old data directly
    sm._data = SessionData(session_id=session_id)
    sm._data.jules_sessions = {"node1": "sess-old"}
    sm._save()

    # Load with NEW SessionManager
    sm2 = SessionManager(session_id)
    sm2.state_dir = tmp_path
    sm2.state_file = tmp_path / f"{session_id}.json"
    sm2._load()

    # Should be able to get it via get_engine_state("jules", "node1")
    assert sm2.get_engine_state("jules", "node1") == "sess-old"
