from rich import box
from rich.panel import Panel

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.pillar import MatrixPillar
from copium_loop.ui.widgets.session import SessionWidget


def test_pillar_render_uses_horizontals_box():
    pillar = MatrixPillar("test")
    panel = pillar.render()
    assert panel.box == box.HORIZONTALS


def test_session_widget_css_removes_vertical_borders():
    css = SessionWidget.DEFAULT_CSS
    # Should not have 'border: solid' or similar that includes vertical lines
    assert "border: solid" not in css
    assert "border-top: solid" in css
    assert "border-bottom: solid" in css

    # Also check focus-within
    assert "border: double" not in css
    assert "border-top: double" in css
    assert "border-bottom: double" in css


def test_session_column_render_uses_horizontals_box():
    session = SessionColumn("test-session")
    layout = session.render()

    # Check header panel
    header_panel = layout["header"].renderable
    assert isinstance(header_panel, Panel)
    assert header_panel.box == box.HORIZONTALS

    # Check workflow status panel (when failed)
    session.workflow_status = "failed"
    layout = session.render()
    status_panel = layout["workflow_status"].renderable
    assert isinstance(status_panel, Panel)
    assert status_panel.box == box.HORIZONTALS
