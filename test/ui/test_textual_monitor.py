import json

import pytest

from copium_loop.ui.textual_dashboard import SessionWidget, TextualDashboard


@pytest.mark.asyncio
async def test_textual_dashboard_discovery(tmp_path):
    # Create a dummy log file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test-session.jsonl"
    log_file.write_text(
        json.dumps(
            {
                "node": "workflow",
                "event_type": "workflow_status",
                "data": "running",
                "timestamp": "2026-02-09T12:00:00",
            }
        )
        + "\n"
    )

    app = TextualDashboard(log_dir=log_dir)
    async with app.run_test() as pilot:
        # Check if session widget was created
        assert "test-session" in app.session_widgets
        session_widget = app.query_one(SessionWidget)
        assert session_widget.session_id == "test-session"

        # Add more data to the log file
        with open(log_file, "a") as f:
            f.write(
                json.dumps(
                    {
                        "node": "coder",
                        "event_type": "status",
                        "data": "active",
                        "timestamp": "2026-02-09T12:00:01",
                    }
                )
                + "\n"
            )

        # Trigger update (normally happens via interval)
        app.update_from_logs()
        await pilot.pause()

        coder_pillar = app.query_one("#pillar-test-session-coder")
        assert coder_pillar.pillar.status == "active"


@pytest.mark.asyncio
async def test_textual_dashboard_switch_tmux(tmp_path, monkeypatch):
    # Create a dummy log file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "test-session.jsonl").write_text("{}\n")

    app = TextualDashboard(log_dir=log_dir)

    switched_to = []

    def mock_switch(sid):
        switched_to.append(sid)

    # Mock it in the original module
    monkeypatch.setattr("copium_loop.ui.tmux.switch_to_tmux_session", mock_switch)

    async with app.run_test() as pilot:
        # We need to wait for the session to be discovered
        app.update_from_logs()
        await pilot.pause()

        assert "test-session" in app.session_widgets

        # Trigger switch action
        await pilot.press("1")
        assert "test-session" in switched_to


@pytest.mark.asyncio
async def test_textual_dashboard_toggle_stats(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "test.jsonl").write_text("{}\n")

    app = TextualDashboard(log_dir=log_dir)
    async with app.run_test() as pilot:
        stats_bar = app.query_one("#stats-bar")
        assert "hidden" not in stats_bar.classes

        # Press 'v' to toggle
        await pilot.press("v")
        assert "hidden" in stats_bar.classes

        # Press 'v' again to show
        await pilot.press("v")
        assert "hidden" not in stats_bar.classes


@pytest.mark.asyncio
async def test_textual_dashboard_navigation(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    # Create two sessions
    (log_dir / "session-a.jsonl").write_text("{}\n")
    (log_dir / "session-b.jsonl").write_text("{}\n")

    app = TextualDashboard(log_dir=log_dir)
    async with app.run_test() as pilot:
        app.update_from_logs()
        await pilot.pause()

        # Initial focus should be on the first session (session-a or session-b depending on sort)
        sorted_sids = app.get_sorted_session_ids()
        assert len(sorted_sids) == 2

        # Press tab to focus first session
        app.action_next_session()
        await pilot.pause()
        focused = app.focused
        if not isinstance(focused, SessionWidget):
            focused = next(
                a for a in focused.ancestors_with_self if isinstance(a, SessionWidget)
            )
        assert focused.session_id == sorted_sids[0]

        # Press tab again to focus second session
        app.action_next_session()
        await pilot.pause()
        focused = app.focused
        if not isinstance(focused, SessionWidget):
            focused = next(
                a for a in focused.ancestors_with_self if isinstance(a, SessionWidget)
            )
        assert focused.session_id == sorted_sids[1]

        # Press tab again to wrap around
        app.action_next_session()
        await pilot.pause()
        focused = app.focused
        if not isinstance(focused, SessionWidget):
            focused = next(
                a for a in focused.ancestors_with_self if isinstance(a, SessionWidget)
            )
        assert focused.session_id == sorted_sids[0]

        # Press shift+tab to go back
        app.action_prev_session()
        await pilot.pause()
        focused = app.focused
        if not isinstance(focused, SessionWidget):
            focused = next(
                a for a in focused.ancestors_with_self if isinstance(a, SessionWidget)
            )
        assert focused.session_id == sorted_sids[1]
