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
        self.border_title = pillar.get_header_text()

        if pillar.status == "active":
            border_style = "#00FF41"
        elif pillar.status in pillar.SUCCESS_STATUSES:
            border_style = "cyan"
        elif pillar.status in pillar.FAILURE_STATUSES:
            border_style = "red"
        else:
            border_style = "#666666"

        self.styles.border = ("round", border_style)
        self.update(pillar.get_content_renderable())
