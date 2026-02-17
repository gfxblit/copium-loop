from copium_loop.ui.pillar import MatrixPillar
from copium_loop.ui.widgets.pillar import PillarWidget


def test_pillar_widget_updates_from_pillar():
    pillar = MatrixPillar("coder")
    widget = PillarWidget(node_id="coder")

    pillar.set_status("active")
    widget.update_from_pillar(pillar)

    assert "▶ CODER" in str(widget.border_title)
    assert widget.border_title_align == "center"
    assert widget.border_subtitle_align == "center"
