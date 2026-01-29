import json

from copium_loop.ui import Dashboard


def test_session_removal_when_file_deleted(tmp_path):
    # Initialize Dashboard
    dash = Dashboard()

    # Use tmp_path for log_dir
    dash.log_dir = tmp_path

    # 1. Create multiple .jsonl files
    session1_file = tmp_path / "session1.jsonl"
    session2_file = tmp_path / "session2.jsonl"

    session1_file.write_text(
        json.dumps(
            {
                "node": "coder",
                "event_type": "status",
                "data": "active",
                "timestamp": "2024-01-01T00:00:00",
            }
        )
        + "\n"
    )
    session2_file.write_text(
        json.dumps(
            {
                "node": "coder",
                "event_type": "status",
                "data": "active",
                "timestamp": "2024-01-01T00:00:00",
            }
        )
        + "\n"
    )

    # 2. Update and assert sessions are created
    dash.update_from_logs()
    assert "session1" in dash.sessions
    assert "session2" in dash.sessions
    assert "session1" in dash.log_offsets
    assert "session2" in dash.log_offsets

    # 3. Delete one .jsonl file
    session1_file.unlink()

    # 4. Update again and assert session1 is removed
    dash.update_from_logs()

    assert "session1" not in dash.sessions, (
        "session1 should have been removed from dash.sessions"
    )
    assert "session2" in dash.sessions
    assert "session1" not in dash.log_offsets, (
        "session1 should have been removed from dash.log_offsets"
    )
    assert "session2" in dash.log_offsets


def test_pagination_clamping_after_removal(tmp_path):
    dash = Dashboard()
    dash.log_dir = tmp_path
    dash.sessions_per_page = 1

    # Create 2 sessions
    (tmp_path / "s1.jsonl").write_text(
        json.dumps(
            {
                "node": "coder",
                "event_type": "status",
                "data": "active",
                "timestamp": "2024-01-01T00:00:00",
            }
        )
        + "\n"
    )
    (tmp_path / "s2.jsonl").write_text(
        json.dumps(
            {
                "node": "coder",
                "event_type": "status",
                "data": "active",
                "timestamp": "2024-01-01T00:00:01",
            }
        )
        + "\n"
    )

    dash.update_from_logs()
    assert len(dash.sessions) == 2

    # Go to page 1 (second page)
    dash.current_page = 1

    # Delete both sessions
    (tmp_path / "s1.jsonl").unlink()
    (tmp_path / "s2.jsonl").unlink()

    dash.update_from_logs()

    # We also need to call make_layout because that's where clamping happens currently
    dash.make_layout()

    assert len(dash.sessions) == 0
    assert dash.current_page == 0
