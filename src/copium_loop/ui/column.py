import time

from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text

from .pillar import MatrixPillar


class SessionColumn:
    """Represents a vertical session column containing stacked agent phases."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._workflow_status = "idle"
        self.created_at = 0
        self.activated_at = 0
        self.completed_at = 0
        self.workflow_status = "running"  # Track workflow-level status
        self.pillars = {
            "coder": MatrixPillar("coder"),
            "tester": MatrixPillar("tester"),
            "architect": MatrixPillar("architect"),
            "reviewer": MatrixPillar("reviewer"),
            "pr_pre_checker": MatrixPillar("pr_pre_checker"),
            "journaler": MatrixPillar("journaler"),
            "pr_creator": MatrixPillar("pr_creator"),
        }

    @property
    def workflow_status(self) -> str:
        return self._workflow_status

    @workflow_status.setter
    def workflow_status(self, value: str):
        if value == "running" and self._workflow_status != "running":
            self.activated_at = time.time()
        elif value in ["success", "failed"] and self._workflow_status == "running":
            self.completed_at = time.time()
        self._workflow_status = value

    @property
    def last_updated(self) -> float:
        """Returns the maximum last_update timestamp across all pillars."""
        return max(pillar.last_update for pillar in self.pillars.values())

    def get_pillar(self, node_id: str) -> MatrixPillar:
        """Returns the pillar for the given node_id, creating it if it doesn't exist."""
        if node_id not in self.pillars:
            self.pillars[node_id] = MatrixPillar(node_id)
        return self.pillars[node_id]

    def render(self, column_width: int | None = None) -> Layout:
        col_layout = Layout()

        # Calculate dynamic ratios based on buffer size and activity
        # This makes the windows "flexible" - they grow as they fill
        ratios = {}
        for node, pillar in self.pillars.items():
            # Base ratio is content length + 2 (for header/borders)
            # We add a weight bonus for the active node
            count = len(pillar.buffer)
            weight = count + 2
            if pillar.status == "active":
                weight += 20  # Ensure active node has enough space
            elif pillar.status == "idle" and count == 0:
                weight = 1  # Keep empty idle nodes very small

            ratios[node] = weight

        # Build the column layout dynamically
        layout_elements = [Layout(name="header", size=3)]

        if self.workflow_status in ["success", "failed"]:
            layout_elements.append(Layout(name="workflow_status", size=3))

        for node in self.pillars:
            layout_elements.append(Layout(name=node, ratio=ratios[node]))

        col_layout.split_column(*layout_elements)

        # Render workflow status banner if needed
        if self.workflow_status in ["success", "failed"]:
            if self.workflow_status == "failed":
                status_text = Text(
                    "⚠ WORKFLOW FAILED - MAX RETRIES EXCEEDED",
                    style="bold white on red",
                    justify="center",
                )
                col_layout["workflow_status"].update(
                    Panel(status_text, border_style="red")
                )
            else:  # success
                status_text = Text(
                    "✓ WORKFLOW COMPLETED SUCCESSFULLY",
                    style="bold black on green",
                    justify="center",
                )
                col_layout["workflow_status"].update(
                    Panel(status_text, border_style="green")
                )

        # Dynamically truncate session_id based on available column width
        display_name = self.session_id

        if column_width:
            # Account for: panel borders (2), padding (2)
            available_width = column_width - 4
            header_text = display_name[:available_width]
        else:
            header_text = display_name

        col_layout["header"].update(
            Panel(
                Text(header_text, justify="center", style="bold yellow"),
                border_style="yellow",
            )
        )
        for node, pillar in self.pillars.items():
            col_layout[node].update(pillar.render())

        return col_layout
