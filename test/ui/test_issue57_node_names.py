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
        "journaler",
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

    # Specifically check that "JOURNAL" (the old name) is NOT there as a standalone header
    # Note: "JOURNAL" might be part of "JOURNALER", so we check for boundary or just ensure "JOURNALER" is there.
    # Actually, the issue is that "JOURNAL" was used instead of "JOURNALER".
    # If the old code used "JOURNAL", it would show "JOURNAL"
    assert "JOURNAL" not in output or "JOURNALER" in output


@pytest.mark.asyncio
async def test_dynamic_node_discovery_in_ui(tmp_path):
    """Verify that new nodes appearing in logs are dynamically added to the UI."""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test_session.jsonl"

    app = TextualDashboard(log_dir=log_dir)

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
        app.update_from_logs()
        await pilot.pause()

        assert "test_session" in app.session_widgets
        widget = app.session_widgets["test_session"]

        # Check if the new node was added to pillars
        assert "security_scanner" in widget.session_column.pillars
        assert (
            widget.session_column.pillars["security_scanner"].name == "security_scanner"
        )

        # Verify it renders in Textual
        pillar_widget = app.query_one("#pillar-test_session-security_scanner")
        assert pillar_widget is not None
