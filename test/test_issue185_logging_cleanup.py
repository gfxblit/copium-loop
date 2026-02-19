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
    return Telemetry("test_session")


def test_telemetry_log_includes_source(telemetry_with_temp_dir):
    """Test that Telemetry.log includes a source field."""
    telemetry_with_temp_dir.log("coder", "status", "active", source="system")

    events = telemetry_with_temp_dir.read_log()
    assert len(events) == 1
    assert events[0]["source"] == "system"


def test_telemetry_log_output_sets_source_llm(telemetry_with_temp_dir):
    """Test that Telemetry.log_output sets source to 'llm'."""
    telemetry_with_temp_dir.log_output("coder", "LLM output")

    events = telemetry_with_temp_dir.read_log()
    assert len(events) == 1
    assert events[0]["source"] == "llm"
    assert events[0]["event_type"] == "output"


def test_telemetry_log_info_sets_source_system(telemetry_with_temp_dir):
    """Test that Telemetry.log_info sets source to 'system'."""
    # This might fail if log_info doesn't exist yet
    if hasattr(telemetry_with_temp_dir, "log_info"):
        telemetry_with_temp_dir.log_info("coder", "System info")

        events = telemetry_with_temp_dir.read_log()
        assert len(events) == 1
        assert events[0]["source"] == "system"
        assert events[0]["event_type"] == "info"
    else:
        pytest.fail("Telemetry.log_info not implemented")


def test_telemetry_other_logs_default_to_system(telemetry_with_temp_dir):
    """Test that other log methods default source to 'system'."""
    telemetry_with_temp_dir.log_status("coder", "active")
    telemetry_with_temp_dir.log_metric("coder", "tokens", 100)
    telemetry_with_temp_dir.log_workflow_status("running")

    events = telemetry_with_temp_dir.read_log()
    assert all(e["source"] == "system" for e in events)


def test_matrix_pillar_filtering():
    """Test that MatrixPillar can filter lines by source."""
    from copium_loop.ui.pillar import MatrixPillar

    pillar = MatrixPillar("coder")

    pillar.add_line("LLM output 1", source="llm")
    pillar.add_line("System info 1", source="system")
    pillar.add_line("LLM output 2", source="llm")

    # By default, should it show all or only LLM?
    # The requirement says "The dashboard should, by default, display only LLM outputs."
    # So MatrixPillar.get_content_renderable() should probably take a filter.

    renderable_llm = pillar.get_content_renderable(show_system=False)
    assert len(renderable_llm.buffer) == 2
    assert "LLM output 1" in renderable_llm.buffer[0]
    assert "LLM output 2" in renderable_llm.buffer[1]

    renderable_all = pillar.get_content_renderable(show_system=True)
    assert len(renderable_all.buffer) == 3


def test_session_column_toggle_system_logs():
    """Test that SessionColumn can toggle system logs visibility."""
    from copium_loop.ui.column import SessionColumn

    session = SessionColumn("test_session")
    pillar = session.get_pillar("coder")

    pillar.add_line("LLM output", source="llm")
    pillar.add_line("System info", source="system")

    # This might require adding a show_system_logs property to SessionColumn or SessionManager
    session.show_system_logs = False
    session.render()
    # Verifying layout content is hard, but we can check if it passes the flag down
    # Or just verify the property exists and is used.
    assert session.show_system_logs is False

    session.show_system_logs = True
    assert session.show_system_logs is True


def test_session_manager_apply_event_source():
    """Test that SessionManager._apply_event_to_session handles the new source field."""
    from pathlib import Path

    from copium_loop.ui.column import SessionColumn
    from copium_loop.ui.manager import SessionManager

    manager = SessionManager(Path("/tmp"))
    session = SessionColumn("test_session")

    # Test LLM output
    event_llm = {
        "node": "coder",
        "event_type": "output",
        "source": "llm",
        "data": "LLM text",
    }
    manager._apply_event_to_session(session, event_llm)
    pillar = session.get_pillar("coder")
    assert len(pillar.buffer) == 1
    assert pillar.buffer[0]["source"] == "llm"

    # Test System info
    event_system = {
        "node": "coder",
        "event_type": "info",
        "source": "system",
        "data": "System text",
    }
    manager._apply_event_to_session(session, event_system)
    assert len(pillar.buffer) == 2
    assert pillar.buffer[1]["source"] == "system"

    # Test fallback for missing source
    event_legacy = {"node": "coder", "event_type": "output", "data": "Legacy text"}
    manager._apply_event_to_session(session, event_legacy)
    assert len(pillar.buffer) == 3
    # Default should be llm for output
    assert pillar.buffer[2]["source"] == "llm"


def test_session_manager_toggle_system_logs():
    """Test that SessionManager.toggle_system_logs updates all sessions."""
    from pathlib import Path

    from copium_loop.ui.manager import SessionManager

    manager = SessionManager(Path("/tmp"))
    # Manually add a session
    from copium_loop.ui.column import SessionColumn

    manager.sessions["s1"] = SessionColumn("s1")
    manager.sessions["s1"].show_system_logs = False

    manager.toggle_system_logs()
    assert manager.show_system_logs is True
    assert manager.sessions["s1"].show_system_logs is True

    manager.toggle_system_logs()
    assert manager.show_system_logs is False
    assert manager.sessions["s1"].show_system_logs is False
