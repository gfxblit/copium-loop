import json
import time
from unittest.mock import MagicMock, patch

from rich.console import Console
from rich.layout import Layout

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.dashboard import Dashboard


def test_dashboard_sessions_per_page():
    """Verify Dashboard default sessions_per_page is 3."""
    dash = Dashboard()
    assert dash.sessions_per_page == 3


def test_dashboard_sorting_logic():
    """Verify Dashboard.make_layout sorts sessions by activated_at (oldest first) for running sessions."""
    dash = Dashboard()
    dash.console = Console(width=100)

    # s1 activated first
    s1 = SessionColumn("session_1")
    s1.activated_at = 1000
    # s2 activated second
    s2 = SessionColumn("session_2")
    s2.activated_at = 2000
    # s3 activated third
    s3 = SessionColumn("session_3")
    s3.activated_at = 3000
    # s4 activated fourth
    s4 = SessionColumn("session_4")
    s4.activated_at = 4000

    dash.sessions = {"session_1": s1, "session_2": s2, "session_3": s3, "session_4": s4}

    # We'll mock render to just return a Layout with a recognizable name
    for s in dash.sessions.values():
        s.render = MagicMock(return_value=Layout(name=s.session_id))

    layout = dash.make_layout()

    # In Dashboard.make_layout, it should sort them: s1, s2, s3, s4 (oldest first)
    # On page 0 with sessions_per_page=3, it should show s1, s2, s3

    active_sessions_layout = layout["main"].children
    assert len(active_sessions_layout) == 3
    assert active_sessions_layout[0].renderable.name == "session_1"
    assert active_sessions_layout[1].renderable.name == "session_2"
    assert active_sessions_layout[2].renderable.name == "session_3"

    # Go to next page
    dash.current_page = 1
    layout = dash.make_layout()
    active_sessions_layout = layout["main"].children
    assert len(active_sessions_layout) == 1
    assert active_sessions_layout[0].renderable.name == "session_4"


def test_dashboard_stable_sorting_logic():
    """Verify Dashboard.make_layout stable sorting logic:
    1. workflow_status == "running" comes first.
    2. Preservation of oldest-first order (by activated_at) within running group.
    """
    dash = Dashboard()
    dash.console = Console(width=100)

    # s1 activated first, running
    s1 = SessionColumn("session_1")
    s1.workflow_status = "running"
    s1.activated_at = 1000

    # s2 activated second, running
    s2 = SessionColumn("session_2")
    s2.workflow_status = "running"
    s2.activated_at = 2000

    # s3 activated third, but not running (finished)
    s3 = SessionColumn("session_3")
    s3.workflow_status = "success"
    s3.completed_at = 5000  # Completed latest

    # s4 activated fourth, running
    s4 = SessionColumn("session_4")
    s4.workflow_status = "running"
    s4.activated_at = 4000

    dash.sessions = {"session_1": s1, "session_2": s2, "session_3": s3, "session_4": s4}

    # Mock render
    for s in dash.sessions.values():
        s.render = MagicMock(return_value=Layout(name=s.session_id))

    # Expected order:
    # 1. Running sessions in activation order: s1, s2, s4
    # 2. Non-running sessions: s3

    layout = dash.make_layout()
    active_sessions_layout = layout["main"].children

    assert active_sessions_layout[0].renderable.name == "session_1"
    assert active_sessions_layout[1].renderable.name == "session_2"
    assert active_sessions_layout[2].renderable.name == "session_4"

    dash.current_page = 1
    layout = dash.make_layout()
    active_sessions_layout = layout["main"].children
    assert active_sessions_layout[0].renderable.name == "session_3"


def test_dashboard_new_sorting_logic():
    """
    Verify new sorting logic:
    1. Active work sessions (workflow_status == 'running') always above inactive ones.
    2. Preserve initial presentation order of active sessions.
    3. Append new active sessions at the end of the active list.
    4. No 60s timer/bucket sort.
    """
    dash = Dashboard()

    # Create sessions in order A, B, C
    sA = SessionColumn("session_A")
    sA.workflow_status = "running"
    sB = SessionColumn("session_B")
    sB.workflow_status = "running"
    sC = SessionColumn("session_C")
    sC.workflow_status = "running"

    # Simulate initial discovery order
    dash.sessions = {"session_A": sA, "session_B": sB, "session_C": sC}

    # Mock render
    for s in dash.sessions.values():
        s.render = MagicMock(return_value=Layout(name=s.session_id))

    # Initial order should be A, B, C
    sorted_sessions = dash.get_sorted_sessions()
    assert [s.session_id for s in sorted_sessions] == [
        "session_A",
        "session_B",
        "session_C",
    ]

    # 1. Update session_B to be more recent than A
    # New requirement: preserve initial order.
    sB.pillars["coder"].last_update = time.time() + 100
    sA.pillars["coder"].last_update = time.time()

    sorted_sessions = dash.get_sorted_sessions()
    # Should still be A, B, C
    assert [s.session_id for s in sorted_sessions] == [
        "session_A",
        "session_B",
        "session_C",
    ]

    # 2. Add new active session D
    sD = SessionColumn("session_D")
    sD.workflow_status = "running"
    dash.sessions["session_D"] = sD
    sD.render = MagicMock(return_value=Layout(name=sD.session_id))

    sorted_sessions = dash.get_sorted_sessions()
    # Should be A, B, C, D
    assert [s.session_id for s in sorted_sessions] == [
        "session_A",
        "session_B",
        "session_C",
        "session_D",
    ]

    # 3. Make session_B inactive
    sB.workflow_status = "success"

    sorted_sessions = dash.get_sorted_sessions()
    # Active (A, C, D) should be above Inactive (B)
    # A, C, D should preserve their relative order
    assert [s.session_id for s in sorted_sessions] == [
        "session_A",
        "session_C",
        "session_D",
        "session_B",
    ]

    # 4. Make session_B active again
    # "Append new active sessions at the end of the active list"
    sB.workflow_status = "running"

    sorted_sessions = dash.get_sorted_sessions()
    # A, C, D were already active. B just became active.
    # It should go to the end of the active list.
    assert [s.session_id for s in sorted_sessions] == [
        "session_A",
        "session_C",
        "session_D",
        "session_B",
    ]


def test_dashboard_completed_sessions_sorting():
    """Verify completed sessions are sorted by completion time (newest first)."""
    dash = Dashboard()

    s1 = SessionColumn("s1")
    s1.workflow_status = "success"
    s1.completed_at = 1000

    s2 = SessionColumn("s2")
    s2.workflow_status = "failed"
    s2.completed_at = 3000

    s3 = SessionColumn("s3")
    s3.workflow_status = "success"
    s3.completed_at = 2000

    dash.sessions = {"s1": s1, "s2": s2, "s3": s3}

    # Expected: s2 (3000), s3 (2000), s1 (1000)
    sorted_sessions = dash.get_sorted_sessions()
    assert [s.session_id for s in sorted_sessions] == ["s2", "s3", "s1"]

    # Add a running session - it should come first regardless of time
    s4 = SessionColumn("s4")
    s4.workflow_status = "running"
    s4.activated_at = 5000
    dash.sessions["s4"] = s4

    sorted_sessions = dash.get_sorted_sessions()
    assert [s.session_id for s in sorted_sessions] == ["s4", "s2", "s3", "s1"]


def test_session_removal_when_file_deleted(tmp_path):
    """Test that sessions are removed if their log file is gone."""
    # Initialize Dashboard
    dash = Dashboard()

    # Use tmp_path for log_dir
    dash.log_dir = tmp_path

    # 1. Create multiple .jsonl files
    session1_file = tmp_path / "session1.jsonl"
    session2_file = tmp_path / "session2.jsonl"

    session1_file.write_text(
        json.dumps(
            {
                "node": "coder",
                "event_type": "status",
                "data": "active",
                "timestamp": "2024-01-01T00:00:00",
            }
        )
        + "\n"
    )
    session2_file.write_text(
        json.dumps(
            {
                "node": "coder",
                "event_type": "status",
                "data": "active",
                "timestamp": "2024-01-01T00:00:00",
            }
        )
        + "\n"
    )

    # 2. Update and assert sessions are created
    dash.update_from_logs()
    assert "session1" in dash.sessions
    assert "session2" in dash.sessions
    assert "session1" in dash.log_offsets
    assert "session2" in dash.log_offsets

    # 3. Delete one .jsonl file
    session1_file.unlink()

    # 4. Update again and assert session1 is removed
    dash.update_from_logs()

    assert "session1" not in dash.sessions, (
        "session1 should have been removed from dash.sessions"
    )
    assert "session2" in dash.sessions
    assert "session1" not in dash.log_offsets, (
        "session1 should have been removed from dash.log_offsets"
    )
    assert "session2" in dash.log_offsets


def test_pagination_clamping_after_removal(tmp_path):
    dash = Dashboard()
    dash.log_dir = tmp_path
    dash.sessions_per_page = 1

    # Create 2 sessions
    (tmp_path / "s1.jsonl").write_text(
        json.dumps(
            {
                "node": "coder",
                "event_type": "status",
                "data": "active",
                "timestamp": "2024-01-01T00:00:00",
            }
        )
        + "\n"
    )
    (tmp_path / "s2.jsonl").write_text(
        json.dumps(
            {
                "node": "coder",
                "event_type": "status",
                "data": "active",
                "timestamp": "2024-01-01T00:00:01",
            }
        )
        + "\n"
    )

    dash.update_from_logs()
    assert len(dash.sessions) == 2

    # Go to page 1 (second page)
    dash.current_page = 1

    # Delete both sessions
    (tmp_path / "s1.jsonl").unlink()
    (tmp_path / "s2.jsonl").unlink()

    dash.update_from_logs()

    # We also need to call make_layout because that's where clamping happens currently
    dash.make_layout()

    assert len(dash.sessions) == 0
    assert dash.current_page == 0


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


def test_dashboard_update_from_logs(tmp_path):
    """Test updating dashboard state from log files."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    # Create a dummy log file
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
        {
            "node": "coder",
            "event_type": "output",
            "data": "starting code...\n",
            "timestamp": "2026-01-28T10:00:02",
        },
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
        {
            "node": "coder",
            "event_type": "status",
            "data": "success",
            "timestamp": "2026-01-28T10:00:10",
        },
        {
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "success",
            "timestamp": "2026-01-28T10:00:11",
        },
    ]
    with open(log_file, "a") as f:
        for e in more_events:
            f.write(json.dumps(e) + "\n")

    dash.update_from_logs()
    assert s.pillars["coder"].status == "success"
    assert s.workflow_status == "success"
    assert s.completed_at > 0


def test_dashboard_update_from_logs_error_handling(tmp_path, capsys):
    """Test that Dashboard.update_from_logs reports errors to stderr."""
    dash = Dashboard()
    dash.log_dir = tmp_path

    # Create a log file that we can't open
    log_file = tmp_path / "error_session.jsonl"
    log_file.write_text("{}")

    # Use patch to make 'open' fail for this specific file
    original_open = open

    def mock_open(file, *args, **kwargs):
        if str(file) == str(log_file):
            raise Exception("Simulated file error")
        return original_open(file, *args, **kwargs)

    with patch("builtins.open", side_effect=mock_open):
        dash.update_from_logs()

    captured = capsys.readouterr()
    assert f"Error processing log file {log_file}: Simulated file error" in captured.err


@patch("copium_loop.ui.dashboard.switch_to_tmux_session")
@patch("copium_loop.ui.dashboard.InputReader")
@patch("copium_loop.ui.dashboard.Live")
@patch("copium_loop.ui.dashboard.termios")
@patch("copium_loop.ui.dashboard.tty")
@patch("copium_loop.ui.dashboard.sys.stdin")
def test_key_one_switches_session(
    mock_stdin, _mock_tty, _mock_termios, _mock_live, mock_input_reader_cls, mock_switch
):
    """Test that pressing '1' switches to the first session."""
    dashboard = Dashboard()
    # Create some dummy sessions
    s1 = SessionColumn("session-1")
    s1.workflow_status = "running"
    s1.activated_at = 100

    s2 = SessionColumn("session-2")
    s2.workflow_status = "running"
    s2.activated_at = 200

    dashboard.sessions = {"session-1": s1, "session-2": s2}

    # Setup mocks
    mock_reader = mock_input_reader_cls.return_value
    # Simulate pressing '1' then 'q'
    mock_reader.get_key.side_effect = ["1", "q"]

    mock_stdin.fileno.return_value = 1

    # Run monitor
    with patch.object(dashboard, "update_from_logs"):
        dashboard.run_monitor()

    # Verify switch was called for the first session (session-1)
    mock_switch.assert_called_with("session-1")


@patch("copium_loop.ui.dashboard.switch_to_tmux_session")
@patch("copium_loop.ui.dashboard.Live")
@patch("copium_loop.ui.dashboard.termios")
@patch("copium_loop.ui.dashboard.tty")
def test_key_one_switches_session_real_reader(
    _mock_tty, _mock_termios, _mock_live, mock_switch
):
    """Test that pressing '1' switches to the first session using the real InputReader (mocked stdin)."""
    import os

    dashboard = Dashboard()
    # Create some dummy sessions
    s1 = SessionColumn("session-1")
    s1.workflow_status = "running"
    s1.activated_at = 100

    s2 = SessionColumn("session-2")
    s2.workflow_status = "running"
    s2.activated_at = 200

    dashboard.sessions = {"session-1": s1, "session-2": s2}

    # Create a pipe to simulate stdin
    r, w = os.pipe()

    # Write '1' (switch) and 'q' (quit)
    os.write(w, b"1q")
    os.close(w)

    # Wrap the read end of the pipe in a file object to replace sys.stdin
    with (
        os.fdopen(r, "r") as mock_stdin_f,
        patch("copium_loop.input_reader.sys.stdin", mock_stdin_f),
        patch("copium_loop.ui.dashboard.sys.stdin", mock_stdin_f),
        patch.object(dashboard, "update_from_logs"),
    ):
        dashboard.run_monitor()

    # Verify switch was called for the first session
    mock_switch.assert_called_with("session-1")
