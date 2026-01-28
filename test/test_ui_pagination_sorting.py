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
    """Verify Dashboard.make_layout sorts sessions by activated_at (discovery order)."""
    dash = Dashboard()
    dash.console = Console(width=100)

    # Creation order: 1, 2, 3, 4
    s1 = SessionColumn("session_1")
    s2 = SessionColumn("session_2")
    s3 = SessionColumn("session_3")
    s4 = SessionColumn("session_4")

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

    # In Dashboard.make_layout, it should sort them: s1, s2, s3, s4 (discovery order)
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
    2. Preservation of initial presentation order (discovery/activation order).
    """
    dash = Dashboard()
    dash.console = Console(width=100)

    # s1 created first
    s1 = SessionColumn("session_1")
    s1.workflow_status = "running"

    # s2 created second
    s2 = SessionColumn("session_2")
    s2.workflow_status = "running"

    # s3 created third, but not running
    s3 = SessionColumn("session_3")
    s3.workflow_status = "success"

    # s4 created fourth
    s4 = SessionColumn("session_4")
    s4.workflow_status = "running"

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
    # 1. Running sessions in creation order: s1, s2, s4
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
