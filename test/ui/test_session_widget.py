import pytest
from textual.app import App, ComposeResult

from copium_loop.ui.column import SessionColumn
from copium_loop.ui.widgets.pillar import PillarWidget
from copium_loop.ui.widgets.session import SessionWidget


class MockApp(App):
    def compose(self) -> ComposeResult:
        column = SessionColumn("test-session")
        widget = SessionWidget(column)
        yield widget


@pytest.mark.asyncio
async def test_session_widget_contains_pillars():
    app = MockApp()
    async with app.run_test() as pilot:
        session_widget = app.query_one(SessionWidget)
        assert session_widget.session_id == "test-session"

        # Manually trigger refresh to populate pillars
        await session_widget.refresh_ui()
        await pilot.pause()

        # Check if basic pillars are present
        pillars = session_widget.query(PillarWidget)
        assert (
            len(pillars) >= 6
        )  # coder, tester, architect, reviewer, pr_pre_checker, pr_creator

        coder_pillar = session_widget.query_one(
            "#pillar-test-session-coder", PillarWidget
        )
        assert coder_pillar.node_id == "coder"
