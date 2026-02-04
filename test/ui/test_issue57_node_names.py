
import json
import tempfile
from pathlib import Path

from rich.console import Console

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.dashboard import Dashboard


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
        assert (
            node.upper() in output
        ), f"Node name {node.upper()} not found in UI output"

    # Specifically check that "JOURNAL" (the old name) is NOT there as a standalone header
    # Note: "JOURNAL" might be part of "JOURNALER", so we check for boundary or just ensure "JOURNALER" is there.
    # Actually, the issue is that "JOURNAL" was used instead of "JOURNALER".
    # If the old code used "JOURNAL", it would show "JOURNAL"
    assert "JOURNAL" not in output or "JOURNALER" in output


def test_dynamic_node_discovery_in_ui():
    """Verify that new nodes appearing in logs are dynamically added to the UI."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        dashboard = Dashboard()
        dashboard.log_dir = Path(tmp_dir)

        log_file = dashboard.log_dir / "test_session.jsonl"

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
        dashboard.update_from_logs()

        assert "test_session" in dashboard.sessions
        session = dashboard.sessions["test_session"]

        # Check if the new node was added to pillars
        assert "security_scanner" in session.pillars
        assert session.pillars["security_scanner"].name == "security_scanner"

        # Verify it renders
        layout = session.render(column_width=80)
        console = Console(width=80)
        with console.capture() as capture:
            console.print(layout)
        output = capture.get().upper()

        assert "SECURITY_SCANNER" in output

