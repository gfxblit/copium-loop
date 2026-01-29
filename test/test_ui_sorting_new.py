import time
from unittest.mock import MagicMock

from rich.layout import Layout

from copium_loop.ui import Dashboard, SessionColumn


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
    dash.sessions = {
        "session_A": sA,
        "session_B": sB,
        "session_C": sC
    }

    # Mock render
    for s in dash.sessions.values():
        s.render = MagicMock(return_value=Layout(name=s.session_id))

    # Initial order should be A, B, C
    sorted_sessions = dash.get_sorted_sessions()
    assert [s.session_id for s in sorted_sessions] == ["session_A", "session_B", "session_C"]

    # 1. Update session_B to be more recent than A
    # New requirement: preserve initial order.
    sB.pillars["coder"].last_update = time.time() + 100
    sA.pillars["coder"].last_update = time.time()

    sorted_sessions = dash.get_sorted_sessions()
    # Should still be A, B, C
    assert [s.session_id for s in sorted_sessions] == ["session_A", "session_B", "session_C"]

    # 2. Add new active session D
    sD = SessionColumn("session_D")
    sD.workflow_status = "running"
    dash.sessions["session_D"] = sD
    sD.render = MagicMock(return_value=Layout(name=sD.session_id))

    sorted_sessions = dash.get_sorted_sessions()
    # Should be A, B, C, D
    assert [s.session_id for s in sorted_sessions] == ["session_A", "session_B", "session_C", "session_D"]

    # 3. Make session_B inactive
    sB.workflow_status = "success"

    sorted_sessions = dash.get_sorted_sessions()
    # Active (A, C, D) should be above Inactive (B)
    # A, C, D should preserve their relative order
    assert [s.session_id for s in sorted_sessions] == ["session_A", "session_C", "session_D", "session_B"]

    # 4. Make session_B active again
    # "Append new active sessions at the end of the active list"
    sB.workflow_status = "running"

    sorted_sessions = dash.get_sorted_sessions()
    # A, C, D were already active. B just became active.
    # It should go to the end of the active list.
    assert [s.session_id for s in sorted_sessions] == ["session_A", "session_C", "session_D", "session_B"]


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