import json
from unittest.mock import patch

import pytest
from textual.widgets import Static

from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.session import SessionWidget


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

    # Mock CodexbarClient to return None (simulating missing executable or failure)
    with patch("copium_loop.ui.textual_dashboard.CodexbarClient") as MockClient:
        instance = MockClient.return_value
        instance.get_usage.return_value = None
        instance.get_usage_async.return_value = None

        app = TextualDashboard(log_dir=log_dir, enable_polling=False)
        async with app.run_test() as pilot:
            await app.update_from_logs()
            await pilot.pause()

            # Initial page: sessions 0, 1, 2
            assert len(app.query(SessionWidget)) == 3
            assert app.manager.current_page == 0

            # Test initial state
            await app.update_footer_stats()
            stats_text = str(app.query_one("#stats-bar", Static).render())

            # This is expected to FAIL before the fix
            assert "Page 1/2" in stats_text
