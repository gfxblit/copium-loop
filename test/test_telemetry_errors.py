import json
from unittest.mock import MagicMock, patch

from copium_loop.telemetry import Telemetry


def test_write_event_permission_error(tmp_path):
    """Verifies that _write_event handles I/O errors gracefully without crashing the thread."""
    session_id = "test_io_error"
    telemetry = Telemetry(session_id)
    telemetry.log_dir = tmp_path / "readonly"
    telemetry.log_dir.mkdir(parents=True)
    telemetry.log_file = telemetry.log_dir / f"{session_id}.jsonl"

    # Mock open to raise PermissionError
    with patch("builtins.open", side_effect=PermissionError("Permission denied")):
        # This shouldn't crash the background thread/executor
        telemetry._write_event({"node": "test", "event_type": "status", "data": "ok"})
        # If it didn't raise an exception here, we're partially good,
        # but the thread executor would catch it anyway.
        # The key is that the Telemetry instance remains usable.

    assert True


def test_read_log_corrupted_json(tmp_path):
    """Verifies that read_log handles corrupted JSON entries gracefully."""
    session_id = "test_corrupted"
    telemetry = Telemetry(session_id)
    telemetry.log_dir = tmp_path
    telemetry.log_file = tmp_path / f"{session_id}.jsonl"

    with open(telemetry.log_file, "w", encoding="utf-8") as f:
        f.write(json.dumps({"event_type": "status", "data": "ok"}) + "\n")
        f.write("not a json\n")
        f.write(json.dumps({"event_type": "status", "data": "pass"}) + "\n")

    events = telemetry.read_log()
    assert len(events) == 2
    assert events[0]["data"] == "ok"
    assert events[1]["data"] == "pass"


def test_subscriber_error_isolation():
    """Verifies that one failing subscriber doesn't prevent others from receiving events."""
    telemetry = Telemetry("test_subscriber_isolation")

    mock_good = MagicMock()
    mock_bad = MagicMock(side_effect=Exception("Subscriber failure"))

    telemetry.add_subscriber(mock_bad)
    telemetry.add_subscriber(mock_good)

    telemetry._write_event({"node": "test", "event_type": "status", "data": "ok"})

    mock_bad.assert_called_once()
    mock_good.assert_called_once()
