import json

import pytest

from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.session import SessionWidget


@pytest.mark.asyncio
async def test_issue128_hotkeys_select_right_workflow_on_pagination(
    tmp_path, monkeypatch
):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Create 5 sessions (default page size is 3)
    # Sessions are sorted by activation time (oldest first for running)
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

        # Page 1: session-0, session-1, session-2
        # Verify initial page
        visible_widgets = list(app.query(SessionWidget))
        assert len(visible_widgets) == 3
        assert visible_widgets[0].session_id == "session-0"

        # Press '1' on Page 1
        app.action_switch_tmux(1)
        assert switched_to[-1] == "session-0"

        # Go to Page 2
        await app.action_next_page()
        await pilot.pause()

        # Page 2: session-3, session-4
        visible_widgets = list(app.query(SessionWidget))
        assert len(visible_widgets) == 2
        assert visible_widgets[0].session_id == "session-3"

        # Press '1' on Page 2
        # EXPECTED: session-3
        # ACTUAL (BUG): session-0
        app.action_switch_tmux(1)

        # This is where it will fail if the bug is present
        assert switched_to[-1] == "session-3", (
            f"Expected session-3 but got {switched_to[-1]}"
        )

        # Press '2' on Page 2
        # EXPECTED: session-4
        # ACTUAL (BUG): session-1
        app.action_switch_tmux(2)
        assert switched_to[-1] == "session-4", (
            f"Expected session-4 but got {switched_to[-1]}"
        )

        # Press '3' on Page 2 (no 3rd session on page 2)
        # EXPECTED: Should do nothing or handle gracefully
        # ACTUAL (BUG): Selects session-2 (from page 1)
        initial_len = len(switched_to)
        app.action_switch_tmux(3)
        assert len(switched_to) == initial_len, (
            "Should not have switched session as 3 is out of range for Page 2"
        )
