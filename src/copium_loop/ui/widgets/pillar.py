from textual.widgets import Static

from ..pillar import MatrixPillar


class PillarWidget(Static):
    """A widget for a single agent phase."""

    DEFAULT_CSS = """
    PillarWidget {
        height: 1fr;
        min-height: 1;
        margin: 0;
        padding: 0;
        border: round;
    }
    """

    def __init__(self, node_id: str, **kwargs):
        super().__init__(**kwargs)
        self.node_id = node_id
        self.pillar: MatrixPillar | None = None

    def update_from_pillar(self, pillar: MatrixPillar) -> None:
        """Updates the widget content from the pillar state."""
        self.pillar = pillar
        self.border_title = pillar.get_title_text()
        self.border_subtitle = pillar.get_subtitle_text()
        self.border_title_align = "center"
        self.border_subtitle_align = "center"
        self.styles.border = ("round", pillar.get_status_color())
        self.update(pillar.get_content_renderable())
