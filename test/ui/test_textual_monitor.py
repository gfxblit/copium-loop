import json

import pytest

from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.pillar import PillarWidget
from copium_loop.ui.widgets.session import SessionWidget


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

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        # Trigger update
        await app.update_from_logs()
        await pilot.pause()

        # Check if session widget was created
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

        # Trigger update
        await app.update_from_logs()

        # Wait for pillar mount
        import asyncio

        for _ in range(10):
            try:
                app.query_one("#pillar-test-session-coder", PillarWidget)
                break
            except Exception:
                await asyncio.sleep(0.1)

        coder_pillar = app.query_one("#pillar-test-session-coder", PillarWidget)
        assert coder_pillar.pillar.status == "active"


@pytest.mark.asyncio
async def test_textual_dashboard_switch_tmux(tmp_path, monkeypatch):
    # Create a dummy log file
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "test-session.jsonl").write_text(
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

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)

    switched_to = []

    def mock_switch(sid):
        switched_to.append(sid)

    # Mock it in the original module
    monkeypatch.setattr("copium_loop.ui.tmux.switch_to_tmux_session", mock_switch)

    async with app.run_test() as pilot:
        # We need to wait for the session to be discovered
        await app.update_from_logs()
        await pilot.pause()

        assert app.query(SessionWidget)

        # Trigger switch action
        await pilot.press("1")
        assert "test-session" in switched_to


@pytest.mark.asyncio
async def test_textual_dashboard_toggle_stats(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "test.jsonl").write_text("{}\n")

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
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
async def test_textual_dashboard_pagination(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create 4 sessions (assuming default page size 3)
    # Timestamps ensure sorted order: s1, s2, s3, s4
    for i in range(1, 5):
        (log_dir / f"s{i}.jsonl").write_text(
            json.dumps(
                {
                    "node": "workflow",
                    "event_type": "workflow_status",
                    "data": "running",
                    "timestamp": f"2026-02-09T12:00:0{i}",
                }
            )
            + "\n"
        )

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    # Ensure stable sort
    app.manager.sessions_per_page = 3

    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        # Page 1: s1, s2, s3 (oldest first)
        widgets = app.query(SessionWidget)
        assert len(widgets) == 3
        sids = [w.session_id for w in widgets]
        assert sids == ["s1", "s2", "s3"]

        # Press Tab to go to next page
        await app.action_next_page()

        # Wait for UI update
        import asyncio

        for _ in range(10):
            widgets = app.query(SessionWidget)
            if len(widgets) == 1 and widgets[0].session_id == "s4":
                break
            await asyncio.sleep(0.1)

        widgets = app.query(SessionWidget)
        assert len(widgets) == 1
        assert widgets[0].session_id == "s4"


@pytest.mark.asyncio
async def test_textual_dashboard_discovered_pillar(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test.jsonl"
    log_file.write_text("{}\n")

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        session_widget = app.query_one(SessionWidget)

        # Initially, 'new-node' should not be in pillars
        assert "new-node" not in session_widget.pillars

        # Add an event for a new node
        with open(log_file, "a") as f:
            f.write(
                json.dumps(
                    {
                        "node": "new-node",
                        "event_type": "status",
                        "data": "active",
                        "timestamp": "2026-02-09T12:00:01",
                    }
                )
                + "\n"
            )

        await app.update_from_logs()

        # Wait for pillar mount
        import asyncio

        for _ in range(10):
            try:
                app.query_one("#pillar-test-new-node", PillarWidget)
                break
            except Exception:
                await asyncio.sleep(0.1)

        # Now it should be there
        assert "new-node" in session_widget.pillars
        new_pillar_widget = app.query_one("#pillar-test-new-node", PillarWidget)
        assert new_pillar_widget.node_id == "new-node"
        assert new_pillar_widget.pillar.status == "active"
