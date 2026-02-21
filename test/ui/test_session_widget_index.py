import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.session import SessionWidget


class SessionWidgetIndexMockApp(App):
    def __init__(self, column=None, index=None):
        super().__init__()
        self.session_column = column or SessionColumn("test-session")
        self.index = index
        self.session_widget = None

    def compose(self) -> ComposeResult:
        if self.index is not None:
            self.session_widget = SessionWidget(self.session_column, index=self.index)
        else:
            self.session_widget = SessionWidget(self.session_column)
        yield self.session_widget


@pytest.mark.asyncio
async def test_session_widget_displays_index():
    app = SessionWidgetIndexMockApp(index=1)
    async with app.run_test():
        session_widget = app.query_one(SessionWidget)
        # Manually trigger refresh as in other tests
        await session_widget.refresh_ui()

        header = session_widget.query_one("#header-test-session", Static)
        content = str(header.render())

        assert "[1]" in content
        assert "test-session" in content


@pytest.mark.asyncio
async def test_session_widget_no_index():
    app = SessionWidgetIndexMockApp(index=None)
    async with app.run_test():
        session_widget = app.query_one(SessionWidget)
        await session_widget.refresh_ui()
        header = session_widget.query_one("#header-test-session", Static)
        content = str(header.render())
        assert "test-session" in content
        assert "[" not in content
