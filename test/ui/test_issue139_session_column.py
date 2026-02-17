from rich.panel import Panel

from copium_loop.ui.column import SessionColumn


def test_session_column_render_header_subtitle():
    col = SessionColumn("test-session")

    # Test running state
    col.workflow_status = "running"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert isinstance(header_panel, Panel)
    assert header_panel.subtitle is None or header_panel.subtitle == ""

    # Test success state
    col.workflow_status = "success"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert "SUCCESS" in str(header_panel.renderable)
    # Check that there is no workflow_status layout element
    import pytest

    try:
        layout["workflow_status"]
        pytest.fail("workflow_status layout element should have been removed")
    except KeyError:
        pass

    # Test failed state
    col.workflow_status = "failed"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert "FAILED" in str(header_panel.renderable)
