import json

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.manager import SessionManager


def test_manager_sessions_per_page(tmp_path):
    """Verify SessionManager default sessions_per_page is 3."""
    mgr = SessionManager(tmp_path)
    assert mgr.sessions_per_page == 3


def test_manager_sorting_logic(tmp_path):
    """Verify SessionManager.get_sorted_sessions sorts by activated_at (oldest first) for running sessions."""
    mgr = SessionManager(tmp_path)

    # s1 activated first
    s1 = SessionColumn("session_1")
    s1.workflow_status = "running"
    s1.activated_at = 1000
    # s2 activated second
    s2 = SessionColumn("session_2")
    s2.workflow_status = "running"
    s2.activated_at = 2000
    # s3 activated third
    s3 = SessionColumn("session_3")
    s3.workflow_status = "running"
    s3.activated_at = 3000
    # s4 activated fourth
    s4 = SessionColumn("session_4")
    s4.workflow_status = "running"
    s4.activated_at = 4000

    mgr.sessions = {"session_1": s1, "session_2": s2, "session_3": s3, "session_4": s4}

    # Expected: s1, s2, s3, s4 (oldest running first)
    sorted_sessions = mgr.get_sorted_sessions()
    assert [s.session_id for s in sorted_sessions] == [
        "session_1",
        "session_2",
        "session_3",
        "session_4",
    ]


def test_manager_stable_sorting_logic(tmp_path):
    """Verify sorting logic: running first, then completed."""
    mgr = SessionManager(tmp_path)

    s1 = SessionColumn("session_1")
    s1.workflow_status = "running"
    s1.activated_at = 1000

    s2 = SessionColumn("session_2")
    s2.workflow_status = "success"
    s2.completed_at = 5000

    mgr.sessions = {"session_1": s1, "session_2": s2}

    sorted_sessions = mgr.get_sorted_sessions()
    assert sorted_sessions[0].session_id == "session_1"
    assert sorted_sessions[1].session_id == "session_2"


def test_manager_pagination(tmp_path):
    """Test pagination logic."""
    mgr = SessionManager(tmp_path, sessions_per_page=2)

    for i in range(5):
        sid = f"s{i}"
        s = SessionColumn(sid)
        s.workflow_status = "running"
        s.activated_at = i
        mgr.sessions[sid] = s

    # Page 0: s0, s1
    visible, page, total = mgr.get_visible_sessions()
    assert len(visible) == 2
    assert visible[0].session_id == "s0"
    assert visible[1].session_id == "s1"
    assert page == 1
    assert total == 3

    # Next page -> Page 1: s2, s3
    mgr.next_page()
    visible, page, total = mgr.get_visible_sessions()
    assert len(visible) == 2
    assert visible[0].session_id == "s2"
    assert visible[1].session_id == "s3"
    assert page == 2

    # Next page -> Page 2: s4
    mgr.next_page()
    visible, page, total = mgr.get_visible_sessions()
    assert len(visible) == 1
    assert visible[0].session_id == "s4"
    assert page == 3

    # Next page -> loop back to Page 0
    mgr.next_page()
    visible, page, total = mgr.get_visible_sessions()
    assert visible[0].session_id == "s0"
    assert page == 1


def test_manager_update_from_logs(tmp_path):
    """Test updating state from log files."""
    mgr = SessionManager(tmp_path)

    log_file = tmp_path / "session1.jsonl"
    events = [
        {
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "running",
            "timestamp": "2026-01-28T10:00:00",
        },
        {
            "node": "coder",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-01-28T10:00:01",
        },
    ]
    with open(log_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    updates = mgr.update_from_logs()

    assert len(updates) == 1
    assert updates[0]["session_id"] == "session1"
    assert len(updates[0]["events"]) == 2

    assert "session1" in mgr.sessions
    s = mgr.sessions["session1"]
    assert s.workflow_status == "running"
    assert s.pillars["coder"].status == "active"


def test_session_manager_apply_event_source(tmp_path):
    """Test that SessionManager._apply_event_to_session handles the new source field."""
    manager = SessionManager(tmp_path)
    session = SessionColumn("test_session")

    # Test LLM output
    event_llm = {
        "node": "coder",
        "event_type": "output",
        "source": "llm",
        "data": "LLM text",
    }
    manager._apply_event_to_session(session, event_llm)
    pillar = session.get_pillar("coder")
    assert len(pillar.buffer) == 1
    assert pillar.buffer[0]["source"] == "llm"

    # Test System info
    event_system = {
        "node": "coder",
        "event_type": "info",
        "source": "system",
        "data": "System text",
    }
    manager._apply_event_to_session(session, event_system)
    assert len(pillar.buffer) == 2
    assert pillar.buffer[1]["source"] == "system"

    # Test fallback for missing source
    event_legacy = {"node": "coder", "event_type": "output", "data": "Legacy text"}
    manager._apply_event_to_session(session, event_legacy)
    assert len(pillar.buffer) == 3
    # Default should be llm for output
    assert pillar.buffer[2]["source"] == "llm"


def test_session_manager_toggle_system_logs(tmp_path):
    """Test that SessionManager.toggle_system_logs updates all sessions."""
    manager = SessionManager(tmp_path)
    # Manually add a session
    manager.sessions["s1"] = SessionColumn("s1")
    manager.sessions["s1"].show_system_logs = False

    manager.toggle_system_logs()
    assert manager.show_system_logs is True
    assert manager.sessions["s1"].show_system_logs is True

    manager.toggle_system_logs()
    assert manager.show_system_logs is False
    assert manager.sessions["s1"].show_system_logs is False


def test_manager_update_from_logs_nested(tmp_path):
    """Verify update_from_logs handles nested directories and correct sorting."""
    import os
    import time

    mgr = SessionManager(tmp_path, max_sessions=5)

    # Create nested structure
    # efficient: file 0 is oldest, file 9 is newest
    files = []
    base_time = time.time() - 1000

    for i in range(10):
        # Create directories
        d = tmp_path / f"dir_{i}"
        d.mkdir()
        f = d / "log.jsonl"

        # Write content
        event = {
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "running",
            "timestamp": "2026-01-28T10:00:00",
        }
        with open(f, "w") as fh:
            fh.write(json.dumps(event) + "\n")

        # Set mtime
        t = base_time + i * 10
        os.utime(f, (t, t))
        files.append(f)

    # Calling update_from_logs should find the 5 most recent files (files 5-9)
    updates = mgr.update_from_logs()

    assert len(updates) == 5

    # Check session IDs. Since files 5-9 are newest, they should be in the updates.
    # The order in updates is not guaranteed by update_from_logs return value (it's a list),
    # but the session map is updated.

    # Session ID is relative path without suffix
    expected_sids = {
        str(files[i].relative_to(tmp_path).with_suffix("")) for i in range(5, 10)
    }
    actual_sids = {u["session_id"] for u in updates}

    assert actual_sids == expected_sids
