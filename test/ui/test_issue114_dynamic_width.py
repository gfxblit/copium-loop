import json
import pytest
from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.session import SessionWidget

@pytest.mark.asyncio
async def test_sessions_expand_and_fit_narrow_screen(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    # Case 1: One session fills the width
    (log_dir / "session-0.jsonl").write_text(
        json.dumps({"node": "workflow", "event_type": "workflow_status", "data": "running", "timestamp": "2026-02-15T12:00:00"}) + "\n"
    )
    
    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    # size=(width, height)
    async with app.run_test(size=(60, 24)) as pilot:
        await app.update_from_logs()
        await pilot.pause()
        
        sessions = app.query(SessionWidget)
        assert len(sessions) == 1
        # Width should be 60 (no margins now)
        assert sessions[0].region.width == 60

    # Case 2: Three sessions fit on a narrow screen (40 wide)
    for i in range(1, 3):
        (log_dir / f"session-{i}.jsonl").write_text(
            json.dumps({"node": "workflow", "event_type": "workflow_status", "data": "running", "timestamp": f"2026-02-15T12:00:0{i}"}) + "\n"
        )
    
    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test(size=(30, 24)) as pilot:
        await app.update_from_logs()
        await pilot.pause()
        
        sessions = app.query(SessionWidget)
        assert len(sessions) == 3
        # Each should be 10 wide (30/3)
        for session in sessions:
            assert session.region.width == 10
