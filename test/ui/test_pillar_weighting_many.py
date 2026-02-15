import json

import pytest

from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.widgets.pillar import PillarWidget
from copium_loop.ui.widgets.session import SessionWidget


@pytest.mark.asyncio
async def test_pillar_weighting_many_nodes(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test-session.jsonl"

    # Initialize with 10 pillars
    events = []
    for i in range(10):
        events.append(
            {
                "node": f"node-{i}",
                "event_type": "status",
                "data": "idle",
                "timestamp": f"2026-02-09T12:00:{i:02d}",
            }
        )

    # Make one active
    events.append(
        {
            "node": "node-5",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-02-09T12:01:00",
        }
    )

    with open(log_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_from_logs()
        await pilot.pause()

        # All pillars should be mounted
        app.query_one(SessionWidget)

        pillars = app.query(PillarWidget)
        assert len(pillars) >= 10

        node_5_pillar = app.query_one("#pillar-test-session-node-5", PillarWidget)
        node_0_pillar = app.query_one("#pillar-test-session-node-0", PillarWidget)

        assert node_5_pillar.styles.height.value == 50.0
        assert node_0_pillar.styles.height.value == 1.0
