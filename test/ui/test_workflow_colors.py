import pytest
from rich.panel import Panel
from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.utils import get_workflow_status_style
from copium_loop.ui.widgets.session import SessionWidget


class SessionWidgetMockApp(App):
    def __init__(self, column=None):
        super().__init__()
        self.session_column = column or SessionColumn("test-session")
        self.session_widget = None

    def compose(self) -> ComposeResult:
        self.session_widget = SessionWidget(self.session_column)
        yield self.session_widget


def get_rgb(color_name: str) -> tuple[int, int, int]:
    """Helper to convert color names used in tests to RGB tuples for Textual/Rich assertions."""
    mapping = {
        "cyan": (0, 255, 255),
        "red": (255, 0, 0),
        "yellow": (255, 255, 0),
    }
    return mapping.get(color_name, (255, 255, 255))


@pytest.mark.asyncio
async def test_session_widget_workflow_colors():
    col = SessionColumn("test-session")
    app = SessionWidgetMockApp(col)
    async with app.run_test():
        widget = app.session_widget
        header = widget.query_one("#header-test-session", Static)

        for status in ["idle", "running", "success", "failed"]:
            col.workflow_status = status
            await widget.refresh_ui()

            style = get_workflow_status_style(status)
            expected_rgb = get_rgb(style["color"])

            assert header.styles.border.top[1].rgb == expected_rgb
            assert header.styles.color.rgb == expected_rgb


def test_session_column_workflow_colors():
    col = SessionColumn("test-session")

    for status in ["idle", "running", "success", "failed"]:
        col.workflow_status = status
        layout = col.render()
        header_panel = layout["header"].renderable
        assert isinstance(header_panel, Panel)

        style = get_workflow_status_style(status)
        expected_color = style["color"]

        # Check if the expected color is in the style string
        assert expected_color in str(header_panel.renderable.style)
        assert expected_color in str(header_panel.border_style)
