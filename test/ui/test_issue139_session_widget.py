import re

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

        # Helper to get plain text from header content
        def get_plain_content(h):
            content = h.render()
            if not content:
                return ""
            s = str(content.plain) if hasattr(content, "plain") else str(content)
            return re.sub(r"\[.*?\]", "", s)

        # Test running state
        col.workflow_status = "running"
        await widget.refresh_ui()
        header = widget.query_one("#header-test-session", Static)
        assert "SUCCESS" not in get_plain_content(header)
        assert "FAILED" not in get_plain_content(header)
        assert header.styles.border.top[1].rgb == (255, 255, 0)  # yellow

        # Test success state
        col.workflow_status = "success"
        await widget.refresh_ui()
        assert "✓ SUCCESS" in get_plain_content(header)

        # Test failed state
        col.workflow_status = "failed"
        await widget.refresh_ui()
        assert "⚠ FAILED" in get_plain_content(header)
        assert header.styles.border.top[1].rgb == (255, 0, 0)  # red
