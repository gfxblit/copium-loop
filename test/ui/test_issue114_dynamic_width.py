import pytest
from textual.app import App, ComposeResult

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.session import SessionWidget


class MockApp(App):
    def compose(self) -> ComposeResult:
        column = SessionColumn("test-session")
        widget = SessionWidget(column)
        yield widget


@pytest.mark.asyncio
async def test_session_widget_min_width():
    app = MockApp()
    async with app.run_test():
        session_widget = app.query_one(SessionWidget)
        # The value is a Scalar, we want to check its value.
        # min-width: 40 currently, should be 8.
        assert session_widget.styles.min_width.value == 8
