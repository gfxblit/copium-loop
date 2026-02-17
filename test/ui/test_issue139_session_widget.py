from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.session import SessionWidget


class MockApp(App):
    def __init__(self, session_column):
        super().__init__()
        self.session_column = session_column
        self.session_widget = None

    def compose(self) -> ComposeResult:
        self.session_widget = SessionWidget(self.session_column)
        yield self.session_widget


async def test_session_widget_header_status():
    col = SessionColumn("test-session")
    app = MockApp(col)
    async with app.run_test():
        widget = app.session_widget

        # Test running state
        col.workflow_status = "running"
        await widget.refresh_ui()
        header = widget.query_one("#header-test-session", Static)
        assert str(header.border_subtitle) == ""
        assert header.styles.border.top[1].rgb == (255, 255, 0)  # yellow

        # Test success state
        col.workflow_status = "success"
        await widget.refresh_ui()
        assert str(header.border_subtitle) == "✓ SUCCESS"
        assert header.styles.border.top[1].rgb == (
            0,
            128,
            0,
        )  # green (standard CSS green is 0,128,0, but Textual might differ)
        # Actually let's see what Textual uses for "green"
        # In the previous fail: Color(255, 255, 0) was yellow.

        # Test failed state
        col.workflow_status = "failed"
        await widget.refresh_ui()
        assert str(header.border_subtitle) == "⚠ FAILED"
        assert header.styles.border.top[1].rgb == (255, 0, 0)  # red
