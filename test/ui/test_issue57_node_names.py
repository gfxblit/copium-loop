import asyncio
import json

import pytest
from rich.console import Console

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.textual_dashboard import TextualDashboard


def test_actual_node_names_in_ui():
    """Verify that actual node names are used as headers in the UI."""
    session = SessionColumn("test_session")

    # We expect these exact node names to be used (will be capitalized in render)
    expected_nodes = [
        "coder",
        "tester",
        "architect",
        "reviewer",
        "pr_pre_checker",
        "pr_creator",
    ]

    layout = session.render(column_width=80)
    console = Console(width=80)
    with console.capture() as capture:
        console.print(layout)
    output = capture.get().upper()

    for node in expected_nodes:
        # Check if the node name (uppercased) appears in the output
        assert node.upper() in output, (
            f"Node name {node.upper()} not found in UI output"
        )

    # Specifically check that "JOURNALER" is NOT there as a standalone header
    assert "JOURNALER" not in output
    assert "JOURNAL" not in output


@pytest.mark.asyncio
async def test_dynamic_node_discovery_in_ui(tmp_path):
    """Verify that new nodes appearing in logs are dynamically added to the UI."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test_session.jsonl"

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)

    async with app.run_test() as pilot:
        # Create an event for a completely new node
        event = {
            "node": "security_scanner",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-02-03T12:00:00",
        }

        with open(log_file, "w") as f:
            f.write(json.dumps(event) + "\n")

        # Update from logs
        await app.update_from_logs()
        await pilot.pause()

        # Wait for the pillar widget to appear (it's mounted by a background worker)
        widget = app.query_one("#session-test_session")
        assert widget is not None

        # Check if the new node was added to pillars model
        assert "security_scanner" in widget.session_column.pillars

        # Create an event for the journaler node (which is hidden by default)
        journaler_event = {
            "node": "journaler",
            "event_type": "status",
            "data": "active",
            "timestamp": "2026-02-03T12:05:00",
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(journaler_event) + "\n")

        # Update from logs again
        await app.update_from_logs()
        await pilot.pause()

        # Check if journaler was added
        assert "journaler" in widget.session_column.pillars

        # Wait for widget mount
        for _ in range(10):
            try:
                app.query_one("#pillar-test_session-security_scanner")
                break
            except Exception:
                await asyncio.sleep(0.1)

        # Verify it renders in Textual
        pillar_widget = app.query_one("#pillar-test_session-security_scanner")
        assert pillar_widget is not None
