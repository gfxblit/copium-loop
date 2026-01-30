from copium_loop.telemetry import Telemetry


def test_telemetry_log_output_empty():
    """Test log_output with empty chunk."""
    t = Telemetry("test_empty")
    # Should not raise exception or call log
    t.log_output("node", "")


def test_telemetry_log_metric():
    """Test log_metric."""
    t = Telemetry("test_metric")
    t.log_metric("node", "latency", 1.5)
    events = t.read_log()
    assert events[0]["event_type"] == "metric"
    assert events[0]["data"]["name"] == "latency"
    assert events[0]["data"]["value"] == 1.5


def test_get_last_incomplete_node_uncertain(tmp_path, monkeypatch):
    """Test get_last_incomplete_node fallback to coder."""
    monkeypatch.setattr("pathlib.Path.home", lambda: tmp_path)
    t = Telemetry("test_uncertain")
    # Add a status that doesn't fit the expected patterns
    t.log("unknown", "status", "weird")

    node, metadata = t.get_last_incomplete_node()
    assert node == "coder"
    assert metadata["reason"] == "uncertain"


def test_reconstruct_state_pr_failed():
    """Test reconstructing state with pr_failed status."""
    t = Telemetry("test_pr_failed")
    t.log_status("pr_creator", "failed")

    state = t.reconstruct_state()
    assert state["review_status"] == "pr_failed"
