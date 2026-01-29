import json
import time
from unittest.mock import patch

from rich.console import Console
from rich.layout import Layout

from copium_loop.ui import Dashboard, MatrixPillar, SessionColumn


def test_dashboard_get_sorted_sessions():
    """Test session sorting: running first, then by time."""
    dash = Dashboard()

    # Session 1: completed, old
    s1 = SessionColumn("s1")
    s1.workflow_status = "success"
    s1.completed_at = 100

    # Session 2: completed, newer
    s2 = SessionColumn("s2")
    s2.workflow_status = "failed"
    s2.completed_at = 200

    # Session 3: running, old
    s3 = SessionColumn("s3")
    s3.workflow_status = "running"
    s3.activated_at = 50

    # Session 4: running, newer
    s4 = SessionColumn("s4")
    s4.workflow_status = "running"
    s4.activated_at = 150

    dash.sessions = {"s1": s1, "s2": s2, "s3": s3, "s4": s4}

    sorted_sessions = dash.get_sorted_sessions()

    # Expected order:
    # 1. Running, oldest first: s3 (activated_at=50)
    # 2. Running, newer: s4 (activated_at=150)
    # 3. Completed, newest first: s2 (completed_at=200)
    # 4. Completed, oldest: s1 (completed_at=100)

    assert [s.session_id for s in sorted_sessions] == ["s3", "s4", "s2", "s1"]

def test_dashboard_make_layout_no_sessions():
    """Test layout when no sessions are present."""
    dash = Dashboard()
    layout = dash.make_layout()
    assert isinstance(layout, Layout)

    console = Console()
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()
    assert "WAITING FOR SESSIONS..." in output

def test_dashboard_pagination():
    """Test dashboard pagination logic."""
    dash = Dashboard()
    dash.sessions_per_page = 2

    for i in range(5):
        sid = f"s{i}"
        s = SessionColumn(sid)
        s.workflow_status = "running"
        s.activated_at = i
        dash.sessions[sid] = s

    # Page 0: s0, s1
    layout0 = dash.make_layout()
    with dash.console.capture() as capture:
        dash.console.print(layout0)
    output0 = capture.get()
    assert "s0" in output0
    assert "s1" in output0
    assert "s2" not in output0

    # Page 1
    dash.current_page = 1
    layout1 = dash.make_layout()
    with dash.console.capture() as capture:
        dash.console.print(layout1)
    output1 = capture.get()
    assert "s2" in output1
    assert "s3" in output1
    assert "s0" not in output1

    # Page 2
    dash.current_page = 2
    layout2 = dash.make_layout()
    with dash.console.capture() as capture:
        dash.console.print(layout2)
    output2 = capture.get()
    assert "s4" in output2
    assert "s0" not in output2

def test_session_column_status_banners():
    """Test workflow status banners in SessionColumn."""
    s = SessionColumn("test")

    # Success
    s.workflow_status = "success"
    layout = s.render()
    console = Console()
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()
    assert "WORKFLOW COMPLETED SUCCESSFULLY" in output

    # Failed
    s = SessionColumn("test_fail")
    s.workflow_status = "failed"
    layout = s.render()
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()
    assert "WORKFLOW FAILED" in output

def test_matrix_pillar_time_suffix():
    """Test time suffix rendering in MatrixPillar."""
    pillar = MatrixPillar("Coder")

    # Active
    pillar.start_time = time.time() - 65 # 1m 5s
    pillar.status = "active"
    panel = pillar.render()
    console = Console()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()
    assert "1m 5s" in output

    # Success with completion time
    pillar.status = "success"
    pillar.completion_time = time.time()
    pillar.duration = 65
    panel = pillar.render()
    with console.capture() as capture:
        console.print(panel)
    output = capture.get()
    assert "1m 5s" in output
    assert "@" in output # Time of completion

def test_dashboard_switch_to_tmux_session():
    """Test switching tmux sessions (mocked)."""
    from copium_loop.ui import switch_to_tmux_session
    with patch("subprocess.run") as mock_run, patch.dict("os.environ", {"TMUX": "/tmp/tmux-1234/default,1234,0"}):
        switch_to_tmux_session("target_session")
        mock_run.assert_called_once_with(
            ["tmux", "switch-client", "-t", "--", "target_session"],
            check=True,
            capture_output=True,
            text=True,
        )

def test_dashboard_update_from_logs(tmp_path):
    """Test updating dashboard state from log files."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    # Create a dummy log file
    log_file = tmp_path / "session1.jsonl"
    events = [
        {"node": "workflow", "event_type": "workflow_status", "data": "running", "timestamp": "2026-01-28T10:00:00"},
        {"node": "coder", "event_type": "status", "data": "active", "timestamp": "2026-01-28T10:00:01"},
        {"node": "coder", "event_type": "output", "data": "starting code...\n", "timestamp": "2026-01-28T10:00:02"},
    ]
    with open(log_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    dash.update_from_logs()

    assert "session1" in dash.sessions
    s = dash.sessions["session1"]
    assert s.workflow_status == "running"
    assert s.pillars["coder"].status == "active"
    assert "starting code..." in s.pillars["coder"].buffer

    # Update with more events
    more_events = [
        {"node": "coder", "event_type": "status", "data": "success", "timestamp": "2026-01-28T10:00:10"},
        {"node": "workflow", "event_type": "workflow_status", "data": "success", "timestamp": "2026-01-28T10:00:11"},
    ]
    with open(log_file, "a") as f:
        for e in more_events:
            f.write(json.dumps(e) + "\n")

    dash.update_from_logs()
    assert s.pillars["coder"].status == "success"
    assert s.workflow_status == "success"
    assert s.completed_at > 0

def test_dashboard_stale_session_removal(tmp_path):
    """Test that sessions are removed if their log file is gone."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    # Create session1
    (tmp_path / "session1.jsonl").write_text("{}")
    dash.update_from_logs()
    assert "session1" in dash.sessions

    # Remove log file
    (tmp_path / "session1.jsonl").unlink()
    dash.update_from_logs()
    assert "session1" not in dash.sessions
