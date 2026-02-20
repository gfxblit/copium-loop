import pytest
from textual.app import App, ComposeResult

from copium_loop.ui.pillar import MatrixPillar
from copium_loop.ui.widgets.pillar import PillarWidget


class MockApp(App):
    def compose(self) -> ComposeResult:
        yield PillarWidget("coder", id="pillar-coder")


@pytest.mark.asyncio
async def test_pillar_widget_updates_content():
    app = MockApp()
    async with app.run_test():
        pillar_widget = app.query_one(PillarWidget)
        pillar = MatrixPillar("coder")
        pillar.add_line("First line")
        pillar_widget.update_from_pillar(pillar)

        assert "First line" in str(pillar_widget.pillar.buffer)

        pillar.set_status("active")
        pillar_widget.update_from_pillar(pillar)
        assert pillar_widget.pillar.status == "active"


def test_pillar_widget_updates_from_pillar():
    pillar = MatrixPillar("coder")
    widget = PillarWidget(node_id="coder")

    pillar.set_status("active")
    widget.update_from_pillar(pillar)

    assert "▶ CODER" in str(widget.border_title)
    assert widget.styles.border_title_align == "center"
    assert widget.styles.border_subtitle_align == "center"
