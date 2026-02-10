import sys

import pytest
from textual.app import App
from textual.widgets import Footer, Header, Static

# Add the packages directory to sys.path
sys.path.append(
    "/Users/billyc/.gemini/tmp/a499af2559971d4c1a2b1a50470dc393bedcc865c437e2e113327bd4c0a93c14/packages"
)


class MonitorApp(App):
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self):
        yield Header()
        yield Static("Copium Loop Monitor", id="main-content")
        yield Footer()


@pytest.mark.asyncio
async def test_app_starts():
    app = MonitorApp()
    async with app.run_test() as pilot:
        assert app.title == "MonitorApp"
        assert app.is_running
        await pilot.press("q")
    assert not app.is_running
