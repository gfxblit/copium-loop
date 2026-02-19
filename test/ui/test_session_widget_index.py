import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.session import SessionWidget


class MockApp(App):
    def compose(self) -> ComposeResult:
        # Create a session widget with an index
        column = SessionColumn("session-with-index")
        widget = SessionWidget(column, index=1, id="widget-1")
        yield widget

        # Create a session widget without an index
        column2 = SessionColumn("session-without-index")
        widget2 = SessionWidget(column2, id="widget-2")
        yield widget2


@pytest.mark.asyncio
async def test_session_widget_index_display():
    app = MockApp()
    async with app.run_test() as pilot:
        widget1 = app.query_one("#widget-1", SessionWidget)
        widget2 = app.query_one("#widget-2", SessionWidget)

        # Trigger refresh
        await widget1.refresh_ui()
        await widget2.refresh_ui()
        await pilot.pause()

        # Check header content for widget 1
        header1 = widget1.query_one(f"#header-{widget1.session_id}", Static)
        # Should contain "[1]"
        assert "[1]" in str(header1.render())
        assert "session-with-index" in str(header1.render())

        # Check header content for widget 2
        header2 = widget2.query_one(f"#header-{widget2.session_id}", Static)
        # Should NOT contain "[2]" or "[]"
        renderable_str = str(header2.render())
        assert "[" not in renderable_str
        assert "]" not in renderable_str
        assert "session-without-index" in renderable_str
