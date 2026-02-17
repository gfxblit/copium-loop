import re
from rich.text import Text
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

        # Helper to get plain text from border subtitle
        def get_plain_subtitle(h):
            sub = h.border_subtitle
            if not sub:
                return ""
            # Textual might return a string with markup if it's internal
            s = str(sub.plain) if hasattr(sub, "plain") else str(sub)
            return re.sub(r"\[.*?\]", "", s)

        # Test running state
        col.workflow_status = "running"
        await widget.refresh_ui()
        header = widget.query_one("#header-test-session", Static)
        assert get_plain_subtitle(header) == ""
        assert header.styles.border.top[1].rgb == (255, 255, 0)  # yellow

        # Test success state
        col.workflow_status = "success"
        await widget.refresh_ui()
        assert get_plain_subtitle(header) == "✓ SUCCESS"

        # Test failed state
        col.workflow_status = "failed"
        await widget.refresh_ui()
        assert get_plain_subtitle(header) == "⚠ FAILED"
        assert header.styles.border.top[1].rgb == (255, 0, 0)  # red
