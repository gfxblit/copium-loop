import pytest
from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.session import SessionWidget


class SessionWidgetMockApp(App):
    def __init__(self, column=None):
        super().__init__()
        self.session_column = column or SessionColumn("test-session")
        self.session_widget = None

    def compose(self) -> ComposeResult:
        self.session_widget = SessionWidget(self.session_column)
        yield self.session_widget


@pytest.mark.asyncio
async def test_session_widget_workflow_colors():
    col = SessionColumn("test-session")
    app = SessionWidgetMockApp(col)
    async with app.run_test():
        widget = app.session_widget
        header = widget.query_one("#header-test-session", Static)

        # Yellow: Outcome not yet determined (states: idle, running).
        col.workflow_status = "idle"
        await widget.refresh_ui()
        assert header.styles.border.top[1].rgb == (255, 255, 0)  # yellow
        assert header.styles.color.rgb == (255, 255, 0)  # yellow text

        col.workflow_status = "running"
        await widget.refresh_ui()
        assert header.styles.border.top[1].rgb == (255, 255, 0)  # yellow
        assert header.styles.color.rgb == (255, 255, 0)  # yellow text

        # Cyan: Workflow terminated successfully (success).
        col.workflow_status = "success"
        await widget.refresh_ui()
        assert header.styles.border.top[1].rgb == (0, 255, 255)  # cyan
        assert header.styles.color.rgb == (0, 255, 255)  # cyan text

        # Red: Workflow terminated with failure (failed).
        col.workflow_status = "failed"
        await widget.refresh_ui()
        assert header.styles.border.top[1].rgb == (255, 0, 0)  # red
        assert header.styles.color.rgb == (255, 0, 0)  # red text


def test_session_column_workflow_colors():
    col = SessionColumn("test-session")

    # Yellow: Outcome not yet determined (states: idle, running).
    col.workflow_status = "idle"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert isinstance(header_panel, Panel)
    # Check if "yellow" is in the style string of the Text object inside the Panel
    assert "yellow" in str(header_panel.renderable.style)
    assert "yellow" in str(header_panel.border_style)

    col.workflow_status = "running"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert "yellow" in str(header_panel.renderable.style)
    assert "yellow" in str(header_panel.border_style)

    # Cyan: Workflow terminated successfully (success).
    col.workflow_status = "success"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert "cyan" in str(header_panel.renderable.style)
    assert "cyan" in str(header_panel.border_style)

    # Red: Workflow terminated with failure (failed).
    col.workflow_status = "failed"
    layout = col.render()
    header_panel = layout["header"].renderable
    assert "red" in str(header_panel.renderable.style)
    assert "red" in str(header_panel.border_style)
