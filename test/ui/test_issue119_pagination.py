import json

import pytest
from textual.widgets import Static

from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.session import SessionWidget


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

        await app.update_footer_stats()
        stats_text = str(app.query_one("#stats-bar", Static).render())
        assert "Page 1/2" in stats_text

        # Test 'right' key
        await pilot.press("right")
        await pilot.pause()
        assert app.manager.current_page == 1
        assert len(app.query(SessionWidget)) == 2

        await app.update_footer_stats()
        stats_text = str(app.query_one("#stats-bar", Static).render())
        assert "Page 2/2" in stats_text

        # Test 'left' key
        await pilot.press("left")
        await pilot.pause()
        assert app.manager.current_page == 0
        assert len(app.query(SessionWidget)) == 3

        await app.update_footer_stats()
        stats_text = str(app.query_one("#stats-bar", Static).render())
        assert "Page 1/2" in stats_text

        # Test 'n' key
        await pilot.press("n")
        await pilot.pause()
        assert app.manager.current_page == 1
        assert len(app.query(SessionWidget)) == 2

        # Test 'p' key
        await pilot.press("p")
        await pilot.pause()
        assert app.manager.current_page == 0
        assert len(app.query(SessionWidget)) == 3

        # Test 'tab' key
        await pilot.press("tab")
        await pilot.pause()
        assert app.manager.current_page == 1
        assert len(app.query(SessionWidget)) == 2

        # Test 'shift+tab' key
        await pilot.press("shift+tab")
        await pilot.pause()
        assert app.manager.current_page == 0
        assert len(app.query(SessionWidget)) == 3
