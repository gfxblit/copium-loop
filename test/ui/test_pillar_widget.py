import sys

import pytest
from textual.app import App

from copium_loop.ui.textual_dashboard import PillarWidget

# Add the packages directory to sys.path
sys.path.append(
    "/Users/billyc/.gemini/tmp/a499af2559971d4c1a2b1a50470dc393bedcc865c437e2e113327bd4c0a93c14/packages"
)


class MockApp(App):
    def compose(self):
        yield PillarWidget("coder", id="pillar-coder")


@pytest.mark.asyncio
async def test_pillar_widget_updates_content():
    from copium_loop.ui.pillar import MatrixPillar

    app = MockApp()
    async with app.run_test():
        pillar_widget = app.query_one(PillarWidget)
        pillar = MatrixPillar("coder")
        pillar.add_line("First line")
        pillar_widget.update_from_pillar(pillar)

        # In Textual, we might need to wait for a refresh or check the internal state
        assert "First line" in str(pillar_widget.pillar.buffer)

        pillar.set_status("active")
        pillar_widget.update_from_pillar(pillar)
        assert pillar_widget.pillar.status == "active"
