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
