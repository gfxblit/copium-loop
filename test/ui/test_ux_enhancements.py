import json

import pytest
from textual.widgets import Footer

from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.session import SessionWidget


@pytest.mark.asyncio
async def test_dashboard_ux_enhancements(tmp_path):
    """
    Tests UX enhancements:
    1. Footer widget presence (for key bindings).
    2. Empty state label when no sessions exist.
    """
    # Empty log directory
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        # 1. Check for Footer
        assert app.query(Footer), "Footer widget (key bindings) should be present"

        # 2. Check for Empty State Message via ID
        assert app.query("#empty-state-label"), (
            "Empty state label should be present initially"
        )

        # 3. Add a session and check label removal
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

        await app.update_from_logs()
        await pilot.pause()

        # Check that session widget is present
        assert app.query(SessionWidget), (
            "SessionWidget should be present after log update"
        )

        # Check that empty state label is GONE
        assert not app.query("#empty-state-label"), (
            "Empty state label should be gone when sessions exist"
        )

        # 4. Remove session and check label return
        log_file.unlink()

        await app.update_from_logs()
        await pilot.pause()

        # Check that session widget is GONE
        assert not app.query(SessionWidget), (
            "SessionWidget should be gone after log removal"
        )

        # Check that empty state label is BACK
        assert app.query("#empty-state-label"), (
            "Empty state label should return when all sessions are gone"
        )
