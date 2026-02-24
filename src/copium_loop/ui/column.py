from rich import box
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
        self.show_system_logs = False
        self.workflow_status = "running"  # Track workflow-level status
        self.pillars = {
            "coder": MatrixPillar("coder"),
            "tester": MatrixPillar("tester"),
            "architect": MatrixPillar("architect"),
            "reviewer": MatrixPillar("reviewer"),
            "pr_pre_checker": MatrixPillar("pr_pre_checker"),
            "pr_creator": MatrixPillar("pr_creator"),
        }

    @property
    def workflow_status(self) -> str:
        return self._workflow_status

    @workflow_status.setter
    def workflow_status(self, value: str):
        self._workflow_status = value

    @property
    def display_name(self) -> str:
        """Returns the display name for the session, extracting the branch name from the full session ID."""
        return self.session_id.split("/")[-1]

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
            if pillar.status == "active":
                weight = count + 22  # Ensure active node has enough space
            elif count > 0:
                weight = max(4, count + 2)  # Ensure at least 2 lines of content
            else:
                weight = 1

            ratios[node] = weight

        # Build the column layout dynamically
        layout_elements = [Layout(name="header", size=3)]

        for node in self.pillars:
            layout_elements.append(Layout(name=node, ratio=ratios[node]))

        col_layout.split_column(*layout_elements)

        # Dynamically truncate session_id based on available column width
        display_name = self.display_name

        if column_width:
            # Account for: panel borders (2), padding (2)
            available_width = column_width - 4
            header_text = display_name[:available_width]
        else:
            header_text = display_name

        from .utils import get_workflow_status_style

        style = get_workflow_status_style(self.workflow_status)
        header_style = style["color"]
        status_suffix = style["suffix"]

        full_header_text = Text(
            f"{header_text}{status_suffix}",
            justify="center",
            style=f"bold {header_style}",
        )

        col_layout["header"].update(
            Panel(
                full_header_text,
                title_align="center",
                subtitle_align="center",
                border_style=header_style,
                box=box.ROUNDED,
            )
        )
        for node, pillar in self.pillars.items():
            col_layout[node].update(pillar.render(show_system=self.show_system_logs))

        return col_layout
