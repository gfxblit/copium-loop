"""Tests for telemetry log parsing and continuation features."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from copium_loop import telemetry
from copium_loop.telemetry import Telemetry, find_latest_session


@pytest.fixture(autouse=True)
def reset_telemetry_singleton():
    """Reset the telemetry singleton before each test."""
    telemetry._telemetry_instance = None
    yield
    telemetry._telemetry_instance = None


@pytest.fixture
def temp_log_dir(tmp_path):
    """Create a temporary log directory."""
    log_dir = tmp_path / ".copium" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


@pytest.fixture
def telemetry_with_temp_dir(temp_log_dir, monkeypatch):
    """Create a Telemetry instance with a temporary log directory."""
    # Patch Path.home() to return tmp_path
    monkeypatch.setattr(Path, "home", lambda: temp_log_dir.parent.parent)
    return Telemetry("test_session")


def test_get_telemetry_uses_tmux_session_name():
    """Test that get_telemetry uses only the tmux session name when available."""
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = "my-awesome-session\n"

    with patch("subprocess.run", return_value=mock_res) as mock_run:
        t = telemetry.get_telemetry()
        assert t.session_id == "my-awesome-session"
        # Verify we requested ONLY the session name (#S), not pane ID (#D)
        mock_run.assert_called_with(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True,
            text=True,
            check=False,
        )


def test_get_telemetry_fallback_to_timestamp():
    """Test that get_telemetry falls back to session_timestamp when tmux is not available."""
    with (
        patch("subprocess.run", side_effect=Exception("no tmux")),
        patch("time.time", return_value=1234567890),
    ):
        t = telemetry.get_telemetry()
        assert t.session_id == "session_1234567890"


class TestTelemetryLogReading:
    """Tests for reading telemetry logs."""

    def test_read_empty_log(self, telemetry_with_temp_dir):
        """Test reading a non-existent log file."""
        events = telemetry_with_temp_dir.read_log()
        assert events == []

    def test_read_log_with_events(self, telemetry_with_temp_dir):
        """Test reading a log file with events."""
        # Write some events
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "active")

        events = telemetry_with_temp_dir.read_log()
        assert len(events) == 3
        assert events[0]["node"] == "coder"
        assert events[0]["data"] == "active"
        assert events[1]["data"] == "idle"
        assert events[2]["node"] == "tester"

    def test_read_log_with_invalid_json(self, telemetry_with_temp_dir):
        """Test reading a log file with invalid JSON lines."""
        # Write valid and invalid events
        telemetry_with_temp_dir.log_status("coder", "active")

        # Manually append invalid JSON
        with open(telemetry_with_temp_dir.log_file, "a") as f:
            f.write("invalid json line\n")

        telemetry_with_temp_dir.log_status("tester", "active")

        events = telemetry_with_temp_dir.read_log()
        # Should skip the invalid line
        assert len(events) == 2
        assert events[0]["node"] == "coder"
        assert events[1]["node"] == "tester"

    def test_get_formatted_log(self, telemetry_with_temp_dir):
        """Test formatting the session log."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_output("coder", "Writing code...")
        telemetry_with_temp_dir.log_status("tester", "active")

        formatted_log = telemetry_with_temp_dir.get_formatted_log()
        # Verify timestamps are present in [HH:MM:SS] format
        import re
        timestamp_pattern = r"\[\d{2}:\d{2}:\d{2}\]"
        assert re.search(timestamp_pattern + " coder: status: active", formatted_log)
        assert re.search(timestamp_pattern + " coder: output: Writing code...", formatted_log)
        assert re.search(timestamp_pattern + " tester: status: active", formatted_log)

    def test_get_formatted_log_truncation(self, telemetry_with_temp_dir):
        """Test truncation of long output in formatted log."""
        long_output = "x" * 1000
        telemetry_with_temp_dir.log_output("coder", long_output)

        formatted_log = telemetry_with_temp_dir.get_formatted_log()
        # Default max_output_chars is 200
        assert "coder: output: " + "x" * 200 + "... (truncated)" in formatted_log
        assert "[" in formatted_log # Check for timestamp start

    def test_get_formatted_log_filtering_and_windowing(self, telemetry_with_temp_dir):
        """Test metric filtering and head/tail windowing."""
        # Log metric (should be filtered)
        telemetry_with_temp_dir.log_metric("coder", "tokens", 100)

        # Log some status events for different nodes
        telemetry_with_temp_dir.log_status("coder", "start") # Head
        for i in range(150):
            node = "tester" if i < 75 else "reviewer"
            telemetry_with_temp_dir.log_status(node, f"status_{i}")

        formatted_log = telemetry_with_temp_dir.get_formatted_log(max_lines=50)

        # Metrics should be gone
        assert "metric" not in formatted_log

        # Should have head
        assert "coder: status: start" in formatted_log

        # Should have tail
        assert "reviewer: status: status_149" in formatted_log

        # Middle should be missing and specify nodes
        assert "tester: status: status_20" not in formatted_log
        assert "removed middle text" in formatted_log
        assert "from reviewer, tester" in formatted_log

    def test_get_formatted_log_includes_truncated_prompt(self, telemetry_with_temp_dir):
        """Test that prompt events are included and truncated."""
        long_prompt = "p" * 300
        telemetry_with_temp_dir.log("coder", "prompt", long_prompt)

        formatted_log = telemetry_with_temp_dir.get_formatted_log()

        # Verify prompt is present and truncated (default 200 chars)
        expected_part = "coder: prompt: " + "p" * 200
        assert expected_part + "... (truncated)" in formatted_log
        assert "[" in formatted_log


class TestGetLastIncompleteNode:
    """Tests for determining the last incomplete node."""

    def test_no_log_found(self, telemetry_with_temp_dir):
        """Test when no log file exists."""
        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        assert node is None
        assert metadata["reason"] == "no_log_found"

    def test_workflow_completed_success(self, telemetry_with_temp_dir):
        """Test when workflow completed successfully."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "success")
        telemetry_with_temp_dir.log_status("reviewer", "approved")
        telemetry_with_temp_dir.log_status("pr_creator", "success")
        telemetry_with_temp_dir.log_workflow_status("success")

        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        assert node is None
        assert metadata["reason"] == "workflow_completed"
        assert metadata["status"] == "success"

    def test_workflow_completed_failed(self, telemetry_with_temp_dir):
        """Test when workflow failed terminally."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("tester", "failed")
        telemetry_with_temp_dir.log_workflow_status("failed")

        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        assert node is None
        assert metadata["reason"] == "workflow_completed"
        assert metadata["status"] == "failed"

    def test_interrupted_at_coder(self, telemetry_with_temp_dir):
        """Test when workflow interrupted during coder node."""
        telemetry_with_temp_dir.log_status("coder", "active")
        # No idle status - interrupted

        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        assert node == "coder"
        assert metadata["reason"] == "incomplete"

    def test_interrupted_at_tester(self, telemetry_with_temp_dir):
        """Test when workflow interrupted during tester node."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "active")
        # No completion status - interrupted

        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        assert node == "tester"
        assert metadata["reason"] == "incomplete"

    def test_tester_failed_should_resume_at_coder(self, telemetry_with_temp_dir):
        """Test when tester failed, should resume at coder (via conditional)."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "active")
        telemetry_with_temp_dir.log_status("tester", "failed")

        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        # Tester failed, so we should resume at tester (it will route back to coder)
        assert node == "tester"
        assert metadata["reason"] == "incomplete"

    def test_reviewer_rejected_should_resume_at_reviewer(self, telemetry_with_temp_dir):
        """Test when reviewer rejected, should resume at reviewer."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "success")
        telemetry_with_temp_dir.log_status("reviewer", "active")
        telemetry_with_temp_dir.log_status("reviewer", "rejected")

        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        assert node == "reviewer"
        assert metadata["reason"] == "incomplete"

    def test_tester_success_should_resume_at_reviewer(self, telemetry_with_temp_dir):
        """Test when tester succeeded, should resume at reviewer."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "active")
        telemetry_with_temp_dir.log_status("tester", "success")

        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        assert node == "reviewer"
        assert metadata["reason"] == "incomplete"

    def test_reviewer_approved_should_resume_at_pr_pre_checker(
        self,
        telemetry_with_temp_dir,
    ):
        """Test when reviewer approved, should resume at pr_pre_checker."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "success")
        telemetry_with_temp_dir.log_status("reviewer", "approved")

        node, metadata = telemetry_with_temp_dir.get_last_incomplete_node()
        assert node == "pr_pre_checker"
        assert metadata["reason"] == "incomplete"


class TestReconstructState:
    """Tests for reconstructing workflow state from logs."""

    def test_reconstruct_empty_state(self, telemetry_with_temp_dir):
        """Test reconstructing state from empty log."""
        state = telemetry_with_temp_dir.reconstruct_state()
        # Empty log should still initialize retry_count to 0
        assert state == {"retry_count": 0}

    def test_reconstruct_with_prompt(self, telemetry_with_temp_dir):
        """Test reconstructing state with initial prompt."""
        telemetry_with_temp_dir.log_output(
            "coder", "INIT: Starting workflow with prompt: Add hello world function"
        )

        state = telemetry_with_temp_dir.reconstruct_state()
        assert state["prompt"] == "Add hello world function"

    def test_reconstruct_retry_count(self, telemetry_with_temp_dir):
        """Test reconstructing retry count from failures."""
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("tester", "failed")
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("tester", "failed")
        telemetry_with_temp_dir.log_status("reviewer", "rejected")

        state = telemetry_with_temp_dir.reconstruct_state()
        # 2 tester failures + 1 reviewer rejection = 3 retries
        assert state["retry_count"] == 3

    def test_reconstruct_test_output_pass(self, telemetry_with_temp_dir):
        """Test reconstructing test output when tests pass."""
        telemetry_with_temp_dir.log_status("tester", "active")
        telemetry_with_temp_dir.log_status("tester", "success")

        state = telemetry_with_temp_dir.reconstruct_state()
        assert state["test_output"] == "PASS"

    def test_reconstruct_test_output_fail(self, telemetry_with_temp_dir):
        """Test reconstructing test output when tests fail."""
        telemetry_with_temp_dir.log_status("tester", "active")
        telemetry_with_temp_dir.log_status("tester", "failed")

        state = telemetry_with_temp_dir.reconstruct_state()
        assert state["test_output"] == "FAIL"

    def test_reconstruct_review_status_approved(self, telemetry_with_temp_dir):
        """Test reconstructing review status when approved."""
        telemetry_with_temp_dir.log_status("reviewer", "active")
        telemetry_with_temp_dir.log_status("reviewer", "approved")

        state = telemetry_with_temp_dir.reconstruct_state()
        assert state["review_status"] == "approved"

    def test_reconstruct_review_status_rejected(self, telemetry_with_temp_dir):
        """Test reconstructing review status when rejected."""
        telemetry_with_temp_dir.log_status("reviewer", "active")
        telemetry_with_temp_dir.log_status("reviewer", "rejected")

        state = telemetry_with_temp_dir.reconstruct_state()
        assert state["review_status"] == "rejected"

    def test_reconstruct_pr_status(self, telemetry_with_temp_dir):
        """Test reconstructing PR creator status."""
        telemetry_with_temp_dir.log_status("pr_creator", "active")
        telemetry_with_temp_dir.log_status("pr_creator", "success")

        state = telemetry_with_temp_dir.reconstruct_state()
        assert state["review_status"] == "pr_created"

    def test_reconstruct_complete_workflow(self, telemetry_with_temp_dir):
        """Test reconstructing state from a complete workflow run."""
        # Simulate a workflow that failed once then succeeded
        telemetry_with_temp_dir.log_output(
            "coder", "INIT: Starting workflow with prompt: Fix bug in login"
        )
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "active")
        telemetry_with_temp_dir.log_status("tester", "failed")
        # Retry
        telemetry_with_temp_dir.log_status("coder", "active")
        telemetry_with_temp_dir.log_status("coder", "idle")
        telemetry_with_temp_dir.log_status("tester", "active")
        telemetry_with_temp_dir.log_status("tester", "success")
        telemetry_with_temp_dir.log_status("reviewer", "active")
        telemetry_with_temp_dir.log_status("reviewer", "approved")

        state = telemetry_with_temp_dir.reconstruct_state()
        assert state["prompt"] == "Fix bug in login"
        assert state["retry_count"] == 1  # One tester failure
        assert state["test_output"] == "PASS"
        assert state["review_status"] == "approved"


class TestFindLatestSession:
    """Tests for finding the latest session."""

    def test_no_logs_directory(self, tmp_path, monkeypatch):
        """Test when logs directory doesn't exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        session_id = find_latest_session()
        assert session_id is None

    def test_empty_logs_directory(self, temp_log_dir, monkeypatch):
        """Test when logs directory is empty."""
        monkeypatch.setattr(Path, "home", lambda: temp_log_dir.parent.parent)
        session_id = find_latest_session()
        assert session_id is None

    def test_find_latest_session(self, temp_log_dir, monkeypatch):
        """Test finding the most recent session."""
        monkeypatch.setattr(Path, "home", lambda: temp_log_dir.parent.parent)

        # Create multiple log files with different timestamps
        import time

        session1 = temp_log_dir / "session1.jsonl"
        session1.write_text("{}\n")
        time.sleep(0.01)

        session2 = temp_log_dir / "session2.jsonl"
        session2.write_text("{}\n")
        time.sleep(0.01)

        session3 = temp_log_dir / "session3.jsonl"
        session3.write_text("{}\n")

        session_id = find_latest_session()
        assert session_id == "session3"
