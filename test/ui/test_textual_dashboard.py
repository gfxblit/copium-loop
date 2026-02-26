import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from textual.widgets import Static

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
        await pilot.pause()

        # Wait for pillar mount
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

        # Mock action_switch_tmux call
        app.action_switch_tmux(1)
        assert switched_to == ["test-session"]


@pytest.mark.asyncio
async def test_textual_dashboard_pagination(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create 5 sessions (default page size is 3)
    for i in range(5):
        (log_dir / f"session-{i}.jsonl").write_text(
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
    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        # Should see 3 sessions initially
        assert len(app.query(SessionWidget)) == 3

        # Next page
        await app.action_next_page()
        await pilot.pause()
        assert len(app.query(SessionWidget)) == 2

        # Prev page
        await app.action_prev_page()
        await pilot.pause()
        assert len(app.query(SessionWidget)) == 3


@pytest.mark.asyncio
async def test_textual_dashboard_toggle_stats(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test():
        stats_bar = app.query_one("#stats-bar")
        assert "hidden" not in stats_bar.classes

        app.action_toggle_stats()
        assert "hidden" in stats_bar.classes

        app.action_toggle_stats()
        assert "hidden" not in stats_bar.classes


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
        await pilot.pause()

        # Wait for pillar mount
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


@pytest.mark.asyncio
async def test_pagination_key_bindings(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create 5 sessions
    for i in range(5):
        log_file = log_dir / f"session-{i}.jsonl"
        data = {
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "running",
            "timestamp": f"2026-02-09T12:00:0{i}",
        }
        log_file.write_text(json.dumps(data) + "\n")

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        # Initial page: sessions 0, 1, 2
        assert len(app.query(SessionWidget)) == 3
        assert app.manager.current_page == 0

        async def check_pagination(key, expected_page, expected_count):
            await pilot.press(key)
            await pilot.pause()
            assert app.manager.current_page == expected_page
            assert len(app.query(SessionWidget)) == expected_count

            await app.update_footer_stats()
            stats_text = str(app.query_one("#stats-bar", Static).render())
            assert f"Page {expected_page + 1}/2" in stats_text

        # Test initial state
        await app.update_footer_stats()
        stats_text = str(app.query_one("#stats-bar", Static).render())
        assert "Page 1/2" in stats_text

        # Test all keys using the helper
        await check_pagination("right", 1, 2)
        await check_pagination("left", 0, 3)
        await check_pagination("n", 1, 2)
        await check_pagination("p", 0, 3)
        await check_pagination("tab", 1, 2)
        await check_pagination("shift+tab", 0, 3)


@pytest.mark.asyncio
async def test_issue128_hotkeys_select_right_workflow_on_pagination(
    tmp_path, monkeypatch
):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create 5 sessions
    for i in range(5):
        (log_dir / f"session-{i}.jsonl").write_text(
            json.dumps(
                {
                    "node": "workflow",
                    "event_type": "workflow_status",
                    "data": "running",
                    "timestamp": f"2026-02-15T12:00:0{i}",
                }
            )
            + "\n"
        )

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)

    switched_to = []

    def mock_switch(sid):
        switched_to.append(sid)

    monkeypatch.setattr("copium_loop.ui.tmux.switch_to_tmux_session", mock_switch)

    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        # Page 1: session-0, session-1, session-2 (Sorted oldest first for running)
        visible_widgets = list(app.query(SessionWidget))
        assert len(visible_widgets) == 3
        assert visible_widgets[0].session_id == "session-0"

        # Press '1' on Page 1 -> session-0
        app.action_switch_tmux(1)
        assert switched_to[-1] == "session-0"

        # Go to Page 2
        await app.action_next_page()
        await pilot.pause()

        # Page 2: session-3, session-4
        visible_widgets = list(app.query(SessionWidget))
        assert len(visible_widgets) == 2
        assert visible_widgets[0].session_id == "session-3"

        # Press '1' on Page 2 -> session-3
        app.action_switch_tmux(1)
        assert switched_to[-1] == "session-3"

        # Press '2' on Page 2 -> session-4
        app.action_switch_tmux(2)
        assert switched_to[-1] == "session-4"

        # Press '3' on Page 2
        initial_len = len(switched_to)
        app.action_switch_tmux(3)
        assert len(switched_to) == initial_len


@pytest.mark.asyncio
async def test_pagination_fails_without_stats(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create 5 sessions
    for i in range(5):
        log_file = log_dir / f"session-{i}.jsonl"
        data = {
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "running",
            "timestamp": f"2026-02-09T12:00:0{i}",
        }
        log_file.write_text(json.dumps(data) + "\n")

    # Mock GeminiStatsClient to return None
    with patch("copium_loop.ui.textual_dashboard.GeminiStatsClient") as MockClient:
        instance = MockClient.return_value
        instance.get_usage.return_value = None
        instance.get_usage_async.return_value = None

        app = TextualDashboard(log_dir=log_dir, enable_polling=False)

        async with app.run_test() as pilot:
            await app.update_from_logs()
            await pilot.pause()

            assert len(app.query(SessionWidget)) == 3
            assert app.manager.current_page == 0

            await app.update_footer_stats()
            stats_text = str(app.query_one("#stats-bar", Static).render())
            assert "Page 1/2" in stats_text


@pytest.mark.asyncio
async def test_numeric_keys_priority(tmp_path, monkeypatch):
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

    monkeypatch.setattr("copium_loop.ui.tmux.switch_to_tmux_session", mock_switch)

    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        session_widget = app.query_one(SessionWidget)
        session_widget.focus()
        await pilot.pause()
        assert app.focused == session_widget

        # Press '1' - should work due to priority=True
        await pilot.press("1")
        await pilot.pause()
        assert switched_to == ["test-session"]


@pytest.mark.asyncio
async def test_switch_to_tmux_session_uses_socket(monkeypatch):
    from unittest.mock import patch

    from copium_loop.ui.tmux import switch_to_tmux_session

    monkeypatch.setenv("TMUX", "/tmp/tmux-unit-test,123,0")

    with patch("copium_loop.ui.tmux.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0

        switch_to_tmux_session("test-session")

        found = False
        for call in mock_run.call_args_list:
            args = call.args[0]
            if "switch-client" in args and "test-session" in args:
                found = True
                assert "-S" in args
                assert "/tmp/tmux-unit-test" in args
                break
        assert found


@pytest.mark.asyncio
async def test_textual_dashboard_update_footer_stats_guard(tmp_path):
    """Verify that update_footer_stats has a concurrency guard using asyncio.Lock."""
    from unittest.mock import MagicMock

    from copium_loop.ui.textual_dashboard import TextualDashboard

    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    assert hasattr(app, "_stats_lock")
    assert isinstance(app._stats_lock, asyncio.Lock)

    call_count = 0

    async def mock_strategy_get_stats_async():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.01)
        return "stats"

    mock_strategy = MagicMock()
    mock_strategy.get_stats_async = AsyncMock(side_effect=mock_strategy_get_stats_async)
    app.stats_strategies = [mock_strategy]

    async with app.run_test():
        await asyncio.gather(
            app.update_footer_stats(),
            app.update_footer_stats(),
            app.update_footer_stats(),
        )

    assert call_count == 1
