from datetime import datetime

from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static

from ..column import SessionColumn
from .pillar import PillarWidget


class WorkflowStatusWidget(Static):
    """A widget for displaying the overall workflow status."""

    DEFAULT_CSS = """
    WorkflowStatusWidget {
        height: 3;
        margin: 0 1;
        display: none;
    }

    WorkflowStatusWidget.visible {
        display: block;
    }
    """

    def update_status(self, status: str):
        if status == "failed":
            status_text = Text(
                "⚠ WORKFLOW FAILED - MAX RETRIES EXCEEDED",
                style="bold white on red",
                justify="center",
            )
            self.update(Panel(status_text, border_style="red"))
            self.add_class("visible")
        elif status == "success":
            status_text = Text(
                "✓ WORKFLOW COMPLETED SUCCESSFULLY",
                style="bold black on green",
                justify="center",
            )
            self.update(Panel(status_text, border_style="green"))
            self.add_class("visible")
        else:
            self.remove_class("visible")


class SessionWidget(Vertical):
    """A widget for a single session."""

    DEFAULT_CSS = """
    SessionWidget {
        width: 1fr;
        height: 100%;
        border: solid green;
        margin: 0 1;
        min-width: 40;
    }

    SessionWidget:focus-within {
        border: double cyan;
    }

    .session-header {
        background: $surface;
        color: yellow;
        text-align: center;
        text-style: bold;
        height: 3;
        content-align: center middle;
        border-bottom: solid yellow;
    }
    """

    def __init__(self, session_column: SessionColumn, **kwargs):
        super().__init__(**kwargs)
        self.can_focus = True
        self.session_column = session_column
        self.session_id = session_column.session_id
        self.pillars: dict[str, PillarWidget] = {}

    def compose(self) -> ComposeResult:
        yield Static(
            f"{self.session_id}",
            classes="session-header",
            id=f"header-{self.session_id}",
        )
        yield WorkflowStatusWidget(id=f"workflow-status-{self.session_id}")
        with VerticalScroll(id=f"scroll-{self.session_id}"):
            pass

    def on_mount(self) -> None:
        self.run_worker(self.refresh_ui())

    async def refresh_ui(self):
        """Updates the session UI based on the underlying SessionColumn state."""
        # Check if mounted to avoid errors, though run_worker usually handles this context
        if not self.is_mounted:
            return

        try:
            header = self.query_one(f"#header-{self.session_id}", Static)
            time_str = ""
            if self.session_column.activated_at > 0:
                dt = datetime.fromtimestamp(self.session_column.activated_at)
                time_str = f" [{dt.strftime('%H:%M:%S')}]"
            header.update(f"{self.session_id}{time_str}")

            status_widget = self.query_one(
                f"#workflow-status-{self.session_id}", WorkflowStatusWidget
            )
            status_widget.update_status(self.session_column.workflow_status)

            scroll = self.query_one(f"#scroll-{self.session_id}", VerticalScroll)

            for node_id, pillar_data in self.session_column.pillars.items():
                if node_id not in self.pillars:
                    widget = PillarWidget(
                        node_id, id=f"pillar-{self.session_id}-{node_id}"
                    )
                    self.pillars[node_id] = widget
                    await scroll.mount(widget)

                self.pillars[node_id].update_from_pillar(pillar_data)
        except Exception:
            pass
