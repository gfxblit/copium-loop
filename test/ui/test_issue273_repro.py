import json

from copium_loop.ui.manager import SessionManager


def test_issue273_stale_failed_status(tmp_path):
    # Create a log file that ends with a failed status
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_file = log_dir / "test-repo-branch.jsonl"

    events = [
        {
            "timestamp": "2026-02-25T10:00:00",
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "running",
        },
        {
            "timestamp": "2026-02-25T10:00:30",
            "node": "coder",
            "event_type": "output",
            "data": "writing some code",
        },
        {
            "timestamp": "2026-02-25T10:01:00",
            "node": "workflow",
            "event_type": "workflow_status",
            "data": "failed",
        },
    ]

    with open(log_file, "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    manager = SessionManager(log_dir)
    manager.update_from_logs()

    session = manager.sessions["test-repo-branch"]
    assert session.workflow_status == "failed"
    assert len(session.get_pillar("coder").buffer) > 0

    # Now simulate a NEW run starting with explicit "started" telemetry event
    new_event = {
        "timestamp": "2026-02-25T11:00:00",
        "node": "workflow",
        "event_type": "workflow_status",
        "data": "started",
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(new_event) + "\n")

    manager.update_from_logs()
    session = manager.sessions["test-repo-branch"]

    # AFTER FIX: It should have reset the session for the new run
    assert session.workflow_status == "running", "Session should be running after reset"
    assert len(session.get_pillar("coder").buffer) == 0, (
        "Pillars should be cleared after reset"
    )
