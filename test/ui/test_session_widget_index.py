import re

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
        # Pass index if provided
        kwargs = {}
        if self.index is not None:
            kwargs["index"] = self.index

        self.session_widget = SessionWidget(self.session_column, **kwargs)
        yield self.session_widget


@pytest.mark.asyncio
async def test_session_widget_with_index():
    app = SessionWidgetIndexMockApp(index=1)
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)

        # Trigger refresh
        await session_widget.refresh_ui()
        await pilot.pause()

        header = session_widget.query_one(f"#header-{session_widget.safe_id}", Static)
        rendered = str(header.render())

        # Should contain the index prefix
        assert "[1]" in rendered
        assert "test-session" in rendered


@pytest.mark.asyncio
async def test_session_widget_without_index():
    app = SessionWidgetIndexMockApp(index=None)
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)

        # Trigger refresh
        await session_widget.refresh_ui()
        await pilot.pause()

        header = session_widget.query_one(f"#header-{session_widget.safe_id}", Static)
        rendered = str(header.render())

        # Should NOT contain any bracketed number prefix at the start
        assert not re.match(r"^\[\d+\]", rendered.strip())
        assert "test-session" in rendered
