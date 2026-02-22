from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

from ..column import SessionColumn
from .pillar import PillarWidget


class SessionWidget(Vertical):
    """A widget for a single session."""

    DEFAULT_CSS = """
    SessionWidget {
        width: 1fr;
        height: 100%;
        margin: 0;
        min-width: 8;
    }

    SessionWidget:focus-within {
    }

    .session-header {
        background: $surface;
        color: yellow;
        text-align: center;
        text-style: bold;
        height: 3;
        content-align: center middle;
        overflow: hidden;
        text-overflow: ellipsis;
        border: round yellow;
        border-title-align: center;
        border-subtitle-align: center;
    }

    .pillars-container {
        height: 1fr;
        overflow-y: auto;
    }
    """

    def __init__(self, session_column: SessionColumn, **kwargs):
        super().__init__(**kwargs)
        self.can_focus = True
        self.session_column = session_column
        self.session_id = session_column.session_id
        # We don't pre-populate self.pillars here because they need to be mounted in compose or refresh_ui
        self.pillars: dict[str, PillarWidget] = {}

    @property
    def safe_id(self) -> str:
        """Returns a Textual-safe ID (no slashes, etc)."""
        import re

        return re.sub(r"[^a-zA-Z0-9_\-]", "_", self.session_id)

    def compose(self) -> ComposeResult:
        yield Static(
            "",
            classes="session-header",
            id=f"header-{self.safe_id}",
        )
        with Vertical(
            id=f"pillars-container-{self.safe_id}", classes="pillars-container"
        ):
            pass

    def on_mount(self) -> None:
        pass

    async def refresh_ui(self):
        """Updates the session UI based on the underlying SessionColumn state."""
        # Check if mounted to avoid errors, though run_worker usually handles this context
        if not self.is_mounted:
            return

        try:
            header = self.query_one(f"#header-{self.safe_id}", Static)
            header.styles.border_title_align = "center"
            header.styles.border_subtitle_align = "center"
            header.border_title = ""

            status_suffix = ""
            if self.session_column.workflow_status == "success":
                status_suffix = " ✓ SUCCESS"
                header.styles.border = ("round", "green")
                header.styles.color = "green"
            elif self.session_column.workflow_status == "failed":
                status_suffix = " ⚠ FAILED"
                header.styles.border = ("round", "red")
                header.styles.color = "red"
            else:
                header.styles.border = ("round", "yellow")
                header.styles.color = "yellow"

            display_name = self.session_column.display_name
            header.update(f"{display_name}{status_suffix}")
            header.border_subtitle = ""

            container = self.query_one(f"#pillars-container-{self.safe_id}", Vertical)

            for node_id, pillar_data in self.session_column.pillars.items():
                if node_id not in self.pillars:
                    widget = PillarWidget(
                        node_id, id=f"pillar-{self.safe_id}-{node_id}"
                    )
                    self.pillars[node_id] = widget
                    await container.mount(widget)

                widget = self.pillars[node_id]
                widget.update_from_pillar(
                    pillar_data, show_system=self.session_column.show_system_logs
                )

                # Weighting logic:
                # Active nodes should be very prominent.
                # Nodes with history get some space but less than active.
                # Idle nodes without history get minimal space.
                # Lean nodes (tester, pr_pre_checker, pr_creator) are always smaller and fixed.
                is_lean = pillar_data.is_lean_node()

                if is_lean:
                    weight = 1
                    widget.styles.min_height = 3
                elif pillar_data.status == "active":
                    count = len(pillar_data.buffer)
                    # Non-lean active nodes get much more weight
                    weight = 100 + (count * 2)
                    widget.styles.min_height = 4
                elif len(pillar_data.buffer) > 0:
                    count = len(pillar_data.buffer)
                    # Non-lean nodes with history get some weight
                    weight = 10 + count
                    widget.styles.min_height = 4
                else:
                    weight = 1
                    widget.styles.min_height = 3

                widget.styles.height = f"{weight}fr"
        except Exception:
            pass
