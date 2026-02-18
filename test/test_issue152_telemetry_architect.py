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
    return Telemetry("test_session")

def test_tester_success_should_resume_at_architect(telemetry_with_temp_dir):
    """Test when tester succeeded, should resume at architect (with new node_order)."""
    telemetry_with_temp_dir.log_status("coder", "active")
    telemetry_with_temp_dir.log_status("coder", "idle")
    telemetry_with_temp_dir.log_status("tester", "active")
    telemetry_with_temp_dir.log_status("tester", "success")

    node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
    # Now it should be architect, not reviewer
    assert node == "architect"
    assert metadata["reason"] == "incomplete"

def test_architect_success_should_resume_at_reviewer(telemetry_with_temp_dir):
    """Test when architect succeeded, should resume at reviewer."""
    telemetry_with_temp_dir.log_status("coder", "active")
    telemetry_with_temp_dir.log_status("coder", "idle")
    telemetry_with_temp_dir.log_status("tester", "success")
    telemetry_with_temp_dir.log_status("architect", "active")
    telemetry_with_temp_dir.log_status("architect", "success")

    node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
    assert node == "reviewer"
    assert metadata["reason"] == "incomplete"

def test_architect_failed_should_resume_at_architect(telemetry_with_temp_dir):
    """Test when architect failed, should resume at architect."""
    telemetry_with_temp_dir.log_status("coder", "active")
    telemetry_with_temp_dir.log_status("coder", "idle")
    telemetry_with_temp_dir.log_status("tester", "success")
    telemetry_with_temp_dir.log_status("architect", "active")
    telemetry_with_temp_dir.log_status("architect", "failed")

    node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
    assert node == "architect"
    assert metadata["reason"] == "incomplete"
