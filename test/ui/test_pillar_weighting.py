import json

import pytest
from textual.css.scalar import Unit

from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.pillar import PillarWidget


@pytest.mark.asyncio
async def test_pillar_weighting_active_node(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test-session.jsonl"

    # Initialize with some pillars
    events = [
        {
            "node": "coder",
            "event_type": "status",
            "data": "idle",
            "timestamp": "2026-02-09T12:00:00",
        },
        {
            "node": "tester",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-02-09T12:00:01",
        },
    ]
    log_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        # Find pillars
        coder_pillar = app.query_one("#pillar-test-session-coder", PillarWidget)
        tester_pillar = app.query_one("#pillar-test-session-tester", PillarWidget)

        # Check their heights or styles
        coder_height = coder_pillar.styles.height
        tester_height = tester_pillar.styles.height

        assert coder_height.unit == Unit.FRACTION
        assert tester_height.unit == Unit.FRACTION

        # tester is active, should have weight 100 (100 base + 0*2 bonus)
        # coder is idle with 0 buffer, should have weight 1
        assert tester_height.value == 100.0
        assert coder_height.value == 1.0
        assert tester_height.value > coder_height.value
