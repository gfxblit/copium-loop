import pytest
from textual.app import App

from copium_loop.ui.textual_dashboard import PillarWidget, SessionWidget

# Add the packages directory to sys.path


class MockApp(App):
    def compose(self):
        yield SessionWidget("test-session")


@pytest.mark.asyncio
async def test_session_widget_contains_pillars():
    app = MockApp()
    async with app.run_test():
        session_widget = app.query_one(SessionWidget)
        assert session_widget.session_id == "test-session"
        # Check if basic pillars are present
        pillars = session_widget.query(PillarWidget)
        assert (
            len(pillars) >= 6
        )  # coder, tester, architect, reviewer, pr_pre_checker, journaler

        coder_pillar = session_widget.query_one(
            "#pillar-test-session-coder", PillarWidget
        )
        assert coder_pillar.phase_name == "coder"
