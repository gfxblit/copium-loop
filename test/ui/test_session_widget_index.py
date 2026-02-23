import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.session import SessionWidget


class SessionWidgetMockApp(App):
    def __init__(self, column=None, index=None):
        super().__init__()
        self.session_column = column or SessionColumn("test-session")
        self.index = index
        self.session_widget = None

    def compose(self) -> ComposeResult:
        # Use kwargs if possible, or directly modify after init if we can't change signature yet
        try:
            self.session_widget = SessionWidget(self.session_column, index=self.index)
        except TypeError:
            # Fallback for before the change
            self.session_widget = SessionWidget(self.session_column)
            if self.index is not None:
                self.session_widget.index = self.index
        yield self.session_widget


@pytest.mark.asyncio
async def test_session_widget_displays_index():
    col = SessionColumn("test-session")
    app = SessionWidgetMockApp(col, index=1)

    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)

        # Manually trigger refresh to populate header
        await session_widget.refresh_ui()
        await pilot.pause()

        header = session_widget.query_one(f"#header-{session_widget.safe_id}", Static)
        header_text = str(header.render())

        # Check if index is present
        assert "[1]" in header_text
        assert "test-session" in header_text


@pytest.mark.asyncio
async def test_session_widget_no_index():
    col = SessionColumn("test-session")
    app = SessionWidgetMockApp(col, index=None)

    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)

        await session_widget.refresh_ui()
        await pilot.pause()

        header = session_widget.query_one(f"#header-{session_widget.safe_id}", Static)
        header_text = str(header.render())

        assert "test-session" in header_text
        assert "[" not in header_text  # Should not have brackets if no index
