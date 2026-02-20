"""Tests for issue #194: Telemetry isolation between runs."""

from pathlib import Path

import pytest

from copium_loop.telemetry import Telemetry


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary log directory."""
    log_dir = tmp_path / ".copium" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


@pytest.fixture
def telemetry_with_temp_dir(temp_log_dir, monkeypatch):
    """Create a Telemetry instance with a temporary log directory."""
    monkeypatch.setattr(Path, "home", lambda: temp_log_dir.parent.parent)
    return Telemetry("test_session_isolation")


def test_reconstruct_state_isolates_runs(telemetry_with_temp_dir):
    """
    Test that reconstruct_state only considers events after the last INIT: marker.
    Reproduces issue #194.
    """
    # First Run (should be ignored)
    telemetry_with_temp_dir.log_info(
        "coder", "INIT: Starting workflow with prompt: First prompt"
    )
    telemetry_with_temp_dir.log_status("coder", "active")
    telemetry_with_temp_dir.log_status("tester", "failed")
    telemetry_with_temp_dir.log_status("reviewer", "rejected")

    # Second Run (the current one)
    telemetry_with_temp_dir.log_info(
        "coder", "INIT: Starting workflow with prompt: Second prompt"
    )
    telemetry_with_temp_dir.log_status("coder", "active")

    state = telemetry_with_temp_dir.reconstruct_state()

    # Verify prompt is from the second run
    assert state["prompt"] == "Second prompt"

    # Verify statuses from the first run did NOT leak
    assert "test_output" not in state
    assert "review_status" not in state


def test_reconstruct_state_prioritizes_system_info(telemetry_with_temp_dir):
    """
    Test that INIT: markers in LLM output (source='llm') don't hijack the prompt
    if there's a system info marker.
    """
    # System info INIT (the real one)
    telemetry_with_temp_dir.log_info(
        "coder", "INIT: Starting workflow with prompt: Real prompt"
    )

    # LLM output containing INIT: (should be ignored for prompt extraction if it's just output)
    # Actually, the current code looks for "INIT:" in output events too.
    # The requirement is to prioritize system source.
    telemetry_with_temp_dir.log_output(
        "coder", "Some LLM noise: INIT: Starting workflow with prompt: Fake prompt"
    )

    state = telemetry_with_temp_dir.reconstruct_state()

    assert state["prompt"] == "Real prompt"


def test_reconstruct_state_handles_jules_engine_leakage(telemetry_with_temp_dir):
    """Test that engine_name doesn't leak from previous runs."""
    # First Run was Jules
    telemetry_with_temp_dir.log_info(
        "coder", "INIT: Starting workflow with prompt: First prompt"
    )
    telemetry_with_temp_dir.log_output(
        "coder", "Jules session created: https://jules.google.com/session/123"
    )

    # Second Run is Gemini (default, no Jules session yet)
    telemetry_with_temp_dir.log_info(
        "coder", "INIT: Starting workflow with prompt: Second prompt"
    )

    state = telemetry_with_temp_dir.reconstruct_state()
    assert state["engine_name"] == "gemini"


def test_get_last_incomplete_node_isolates_runs(telemetry_with_temp_dir):
    """Test that get_last_incomplete_node doesn't return success from a previous run."""
    # First Run succeeded
    telemetry_with_temp_dir.log_info("coder", "INIT: Starting workflow with prompt: First prompt")
    telemetry_with_temp_dir.log_status("coder", "success")
    telemetry_with_temp_dir.log_workflow_status("success")

    # Second Run is just starting
    telemetry_with_temp_dir.log_info("coder", "INIT: Starting workflow with prompt: Second prompt")
    telemetry_with_temp_dir.log_status("coder", "active")

    node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()

    # It should resume from coder (active in second run)
    assert node == "coder"
    assert metadata["reason"] == "incomplete"
