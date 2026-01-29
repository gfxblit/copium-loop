import json
import time
from unittest.mock import MagicMock

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel

from copium_loop.ui import (
    Dashboard,
    MatrixPillar,
    SessionColumn,
    TailRenderable,
    extract_tmux_session,
)


def test_tail_renderable_basic():
    """Test that TailRenderable renders the last N lines."""
    buffer = ["line 1", "line 2", "line 3", "line 4", "line 5"]
    # We want to fit 3 lines
    renderable = TailRenderable(buffer, status="idle")

    console = Console(width=20, height=3)
    # Mocking options or similar might be needed if TailRenderable uses it
    # For now, let's just see if it handles height
    with console.capture() as capture:
        console.print(renderable)

    output = capture.get()
    # If height is 3, it should show line 3, 4, 5
    assert "line 3" in output
    assert "line 4" in output
    assert "line 5" in output
    assert "line 1" not in output
    assert "line 2" not in output


def test_tail_renderable_wrapping():
    """Test that TailRenderable handles line wrapping when calculating the tail."""
    # Line that will wrap into 2 lines if width is small
    buffer = ["short 1", "this is a very long line that should wrap", "short 2"]
    # width=20, "  this is a very long line that should wrap" is ~44 chars
    # It should wrap into 3 lines:
    # "  this is a very"
    # "long line that"
    # "should wrap"

    # height=3 should show "short 2" and the last 2 lines of the wrapped line
    # Wait, height=3, and we have:
    # L1: "short 2" (1 line)
    # L2: "should wrap" (wrapped part of long line)
    # L3: "long line that" (wrapped part of long line)

    renderable = TailRenderable(buffer, status="idle")
    console = Console(width=20, height=3)
    with console.capture() as capture:
        console.print(renderable)

    output = capture.get()
    assert "short 2" in output
    assert "should wrap" in output
    assert "long line that" in output
    assert "short 1" not in output
    assert "this is a very" not in output


def test_tail_renderable_empty():
    """Test that TailRenderable handles an empty buffer."""
    renderable = TailRenderable([], status="idle")
    console = Console()
    with console.capture() as capture:
        console.print(renderable)
    output = capture.get()
    assert output == ""


def test_matrix_pillar_render_order():
    """Test that MatrixPillar renders logs in chronological order (oldest to newest)."""
    pillar = MatrixPillar("Coder")
    pillar.add_line("first")
    pillar.add_line("second")
    pillar.add_line("third")

    panel = pillar.render()
    assert isinstance(panel, Panel)

    # We need to verify the content of the panel
    console = Console(width=20)
    with console.capture() as capture:
        console.print(panel)

    output = capture.get()
    # Chronological order: first, second, third (top to bottom)
    first_idx = output.find("first")
    second_idx = output.find("second")
    third_idx = output.find("third")

    assert first_idx != -1
    assert second_idx != -1
    assert third_idx != -1
    assert first_idx < second_idx < third_idx


def test_tail_renderable_styling():
    """Test that TailRenderable applies correct styles based on recency and status."""
    buffer = [f"line {i}" for i in range(15)]
    # newest is line 14

    # Test active status (white with > prefix)
    renderable_active = TailRenderable(buffer, status="active")
    console = Console(width=20)
    with console.capture() as capture:
        console.print(renderable_active)
    output_active = capture.get()
    assert "> line 14" in output_active

    # Test idle status (should ALWAYS have > prefix for newest line now)
    renderable_idle = TailRenderable(buffer, status="idle")
    with console.capture() as capture:
        console.print(renderable_idle)
    output_idle = capture.get()
    assert "> line 14" in output_idle
    assert "  line 14" not in output_idle

    # others should have "  "
    assert "  line 13" in output_active
    assert "  line 10" in output_active
    assert "  line 0" in output_active


def test_matrix_pillar_status_and_duration():
    """Test that MatrixPillar correctly tracks status and duration."""
    pillar = MatrixPillar("Coder")

    # Initial state
    assert pillar.status == "idle"
    assert pillar.duration is None

    # Set to active
    timestamp = "2026-01-25T12:00:00"
    pillar.set_status("active", timestamp)
    assert pillar.status == "active"

    # Set to success after 10 seconds
    timestamp_end = "2026-01-25T12:00:10"
    pillar.set_status("success", timestamp_end)
    assert pillar.status == "success"
    assert pillar.duration == 10.0
    assert pillar.completion_time is not None


def test_matrix_pillar_buffer_limit():
    """Test that MatrixPillar respects its max_buffer size."""
    pillar = MatrixPillar("Coder")
    pillar.max_buffer = 5

    for i in range(10):
        pillar.add_line(f"line {i}")

    assert len(pillar.buffer) == 5
    assert pillar.buffer[0] == "line 5"
    assert pillar.buffer[-1] == "line 9"


def test_session_column_rendering():
    """Test that SessionColumn renders its pillars."""
    session = SessionColumn("test_session")

    # Set some content and status
    session.pillars["coder"].add_line("coding...")
    session.pillars["coder"].set_status("active")

    layout = session.render(column_width=40)

    # Verify it renders to console without crashing
    console = Console(width=40)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get()
    assert "test_session" in output
    assert "CODER" in output
    assert "coding..." in output


def test_dashboard_extract_tmux_session():
    """Test that extract_tmux_session correctly parses session IDs."""
    assert extract_tmux_session("my_session") == "my_session"
    assert extract_tmux_session("my_session_0") == "my_session"
    assert extract_tmux_session("my_session_%1") == "my_session"
    assert extract_tmux_session("session_12345678") is None

def test_dashboard_sessions_per_page():
    """Verify Dashboard default sessions_per_page is 3."""
    dash = Dashboard()
    assert dash.sessions_per_page == 3


def test_session_column_last_updated():
    """Verify SessionColumn.last_updated calculates the maximum last_update across pillars."""
    session = SessionColumn("test_session")

    # Manually set last_update for pillars
    now = time.time()
    session.pillars["coder"].last_update = now - 100
    session.pillars["tester"].last_update = now - 50
    session.pillars["reviewer"].last_update = now - 150
    session.pillars["pr_creator"].last_update = now - 200

    assert session.last_updated == now - 50

    # Update one pillar
    session.pillars["reviewer"].last_update = now + 10
    assert session.last_updated == now + 10


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


def test_extract_tmux_session_new_format():
    """Test that extract_tmux_session handles the new session-only format."""
    session_id = "my-awesome-session"
    assert extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_old_format_with_percent():
    """Test that extract_tmux_session still handles the old format with % pane ID."""
    session_id = "my-awesome-session_%179"
    assert extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_old_format_without_percent():
    """Test that extract_tmux_session handles the old format with numeric pane ID."""
    session_id = "my-awesome-session_123"
    assert extract_tmux_session(session_id) == "my-awesome-session"


def test_extract_tmux_session_not_tmux():
    """Test that extract_tmux_session returns None for non-tmux session IDs."""
    session_id = "session_1234567890"
    assert extract_tmux_session(session_id) is None


def test_extract_tmux_session_name_with_underscore():
    """Test that extract_tmux_session handles session names that contain underscores."""
    # If the session name itself has an underscore and we use the new format
    session_id = "my_project_v2"
    # It should return the whole thing because it doesn't end in a pane-like suffix
    assert extract_tmux_session(session_id) == "my_project_v2"


def test_extract_tmux_session_old_format_with_underscore_in_name():
    """Test old format where the session name itself contains an underscore."""
    session_id = "my_project_v2_%5"
    assert extract_tmux_session(session_id) == "my_project_v2"
