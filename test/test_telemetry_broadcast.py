from pathlib import Path

import pytest

from copium_loop.telemetry import Telemetry


@pytest.fixture
def temp_log_dir(tmp_path):
    log_dir = tmp_path / ".copium" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


@pytest.fixture
def telemetry_with_temp_dir(temp_log_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_log_dir.parent.parent)
    return Telemetry("test_broadcast_session")


def test_telemetry_broadcasts_events(telemetry_with_temp_dir):
    received_events = []

    def subscriber(event):
        received_events.append(event)

    telemetry_with_temp_dir.add_subscriber(subscriber)

    telemetry_with_temp_dir.log_status("coder", "active")
    telemetry_with_temp_dir.flush()

    assert len(received_events) == 1
    assert received_events[0]["node"] == "coder"
    assert received_events[0]["event_type"] == "status"
    assert received_events[0]["data"] == "active"


def test_telemetry_remove_subscriber(telemetry_with_temp_dir):
    received_events = []

    def subscriber(event):
        received_events.append(event)

    telemetry_with_temp_dir.add_subscriber(subscriber)
    telemetry_with_temp_dir.remove_subscriber(subscriber)

    telemetry_with_temp_dir.log_status("coder", "active")
    telemetry_with_temp_dir.flush()

    assert len(received_events) == 0
