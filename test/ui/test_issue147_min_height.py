import pytest
from textual.app import App, ComposeResult

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.pillar import PillarWidget
from copium_loop.ui.widgets.session import SessionWidget


class MockApp(App):
    def __init__(self, column: SessionColumn):
        super().__init__()
        self.column = column

    def compose(self) -> ComposeResult:
        yield SessionWidget(self.column)


@pytest.mark.asyncio
async def test_pillar_min_height_with_content():
    column = SessionColumn("test-session")
    coder_pillar = column.get_pillar("coder")
    coder_pillar.add_line("Line 1")
    coder_pillar.status = "idle"

    app = MockApp(column)
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)
        await session_widget.refresh_ui()
        await pilot.pause()

        coder_widget = app.query_one("#pillar-test-session-coder", PillarWidget)
        # CURRENTLY: min_height is 3
        # EXPECTED: min_height should be 4
        assert coder_widget.styles.min_height.value == 4


@pytest.mark.asyncio
async def test_pillar_min_height_when_active():
    column = SessionColumn("test-session")
    coder_pillar = column.get_pillar("coder")
    coder_pillar.status = "active"
    # No lines in buffer

    app = MockApp(column)
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)
        await session_widget.refresh_ui()
        await pilot.pause()

        coder_widget = app.query_one("#pillar-test-session-coder", PillarWidget)
        # CURRENTLY: min_height is 3
        # EXPECTED: min_height should be 4
        assert coder_widget.styles.min_height.value == 4


@pytest.mark.asyncio
async def test_pillar_min_height_when_idle_empty():
    column = SessionColumn("test-session")
    coder_pillar = column.get_pillar("coder")
    coder_pillar.status = "idle"
    # No lines in buffer

    app = MockApp(column)
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)
        await session_widget.refresh_ui()
        await pilot.pause()

        coder_widget = app.query_one("#pillar-test-session-coder", PillarWidget)
        # EXPECTED: min_height should remain 3
        assert coder_widget.styles.min_height.value == 3
