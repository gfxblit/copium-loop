import time
from unittest.mock import MagicMock

from rich.console import Console
from rich.layout import Layout

from copium_loop.ui import Dashboard, SessionColumn


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
    """Verify Dashboard.make_layout sorts sessions by last_updated in descending order."""
    dash = Dashboard()
    dash.console = Console(width=100)

    s1 = SessionColumn("session_1")
    s2 = SessionColumn("session_2")
    s3 = SessionColumn("session_3")
    s4 = SessionColumn("session_4")

    now = time.time()

    # Initialize all pillars to a very old timestamp to avoid interference
    for s in [s1, s2, s3, s4]:
        for pillar in s.pillars.values():
            pillar.last_update = now - 1000

    # session_2 is most recent
    s2.pillars["coder"].last_update = now
    # session_4 is second most recent
    s4.pillars["coder"].last_update = now - 100
    # session_1 is third
    s1.pillars["coder"].last_update = now - 200
    # session_3 is oldest
    s3.pillars["coder"].last_update = now - 300

    dash.sessions = {
        "session_1": s1,
        "session_2": s2,
        "session_3": s3,
        "session_4": s4
    }

    # We'll mock render to just return a Layout with a recognizable name
    for s in dash.sessions.values():
        s.render = MagicMock(return_value=Layout(name=s.session_id))

    layout = dash.make_layout()

    # In Dashboard.make_layout, it should sort them: s2, s4, s1, s3
    # On page 0 with sessions_per_page=3, it should show s2, s4, s1

    active_sessions_layout = layout["main"].children
    assert len(active_sessions_layout) == 3
    assert active_sessions_layout[0].renderable.name == "session_2"
    assert active_sessions_layout[1].renderable.name == "session_4"
    assert active_sessions_layout[2].renderable.name == "session_1"

    # Go to next page
    dash.current_page = 1
    layout = dash.make_layout()
    active_sessions_layout = layout["main"].children
    assert len(active_sessions_layout) == 1
    assert active_sessions_layout[0].renderable.name == "session_3"

def test_dashboard_stable_sorting_logic():
    """Verify Dashboard.make_layout stable sorting logic:
    1. workflow_status == "running" comes first.
    2. last_updated rounded to 60s buckets (descending).
    3. session_id (ascending) as tie-breaker.
    """
    dash = Dashboard()
    dash.console = Console(width=100)

    now = time.time()

    # s1: running, updated 10s ago
    s1 = SessionColumn("session_1")
    s1.workflow_status = "running"
    for p in s1.pillars.values():
        p.last_update = now - 10

    # s2: running, updated 130s ago (definitely different bucket)
    s2 = SessionColumn("session_2")
    s2.workflow_status = "running"
    for p in s2.pillars.values():
        p.last_update = now - 130

    # s3: success, updated 5s ago (most recent, but not running)
    s3 = SessionColumn("session_3")
    s3.workflow_status = "success"
    for p in s3.pillars.values():
        p.last_update = now - 5

    # s4: running, updated 15s ago (same bucket as s1 if no boundary between them)
    s4 = SessionColumn("session_4")
    s4.workflow_status = "running"
    for p in s4.pillars.values():
        p.last_update = now - 15

    dash.sessions = {
        "session_1": s1,
        "session_2": s2,
        "session_3": s3,
        "session_4": s4
    }

    # Mock render
    for s in dash.sessions.values():
        s.render = MagicMock(return_value=Layout(name=s.session_id))

    # Expected order:
    # 1. Running sessions: s1, s4, s2
    #    - s1 and s4 are in the same 60s bucket (now-10 and now-15)
    #    - s1 and s4 should be sorted by session_id: s1, s4
    #    - s2 is in an older bucket (now-70)
    # 2. Non-running sessions: s3

    layout = dash.make_layout()
    active_sessions_layout = layout["main"].children

    assert active_sessions_layout[0].renderable.name == "session_1"
    assert active_sessions_layout[1].renderable.name == "session_4"
    assert active_sessions_layout[2].renderable.name == "session_2"

    dash.current_page = 1
    layout = dash.make_layout()
    active_sessions_layout = layout["main"].children
    assert active_sessions_layout[0].renderable.name == "session_3"
