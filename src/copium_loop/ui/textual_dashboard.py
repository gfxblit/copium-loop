import json
import os
from datetime import datetime
from pathlib import Path

from rich.panel import Panel
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll, Vertical, VerticalScroll
from textual.widgets import Footer, Header, Static

from ..codexbar import CodexbarClient
from .column import SessionColumn
from .footer_stats import CodexStatsStrategy, SystemStatsStrategy


class PillarWidget(Static):
    """A widget for a single agent phase."""

    def __init__(self, phase_name: str, **kwargs):
        super().__init__(**kwargs)
        self.phase_name = phase_name
        self.pillar = None  # Will be set by SessionWidget

    def update_from_pillar(self, pillar):
        self.pillar = pillar
        self.update(self.pillar.render())


class WorkflowStatusWidget(Static):
    """A widget for displaying the overall workflow status."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status = "idle"

    def update_status(self, status: str):
        self.status = status
        if status == "failed":
            status_text = Text(
                "⚠ WORKFLOW FAILED - MAX RETRIES EXCEEDED",
                style="bold white on red",
                justify="center",
            )
            self.update(Panel(status_text, border_style="red"))
            self.display = True
        elif status == "success":
            status_text = Text(
                "✓ WORKFLOW COMPLETED SUCCESSFULLY",
                style="bold black on green",
                justify="center",
            )
            self.update(Panel(status_text, border_style="green"))
            self.display = True
        else:
            self.display = False


class SessionWidget(Vertical):
    """A widget for a single session."""

    def __init__(self, session_id: str, **kwargs):
        super().__init__(**kwargs)
        self.can_focus = True
        self.session_id = session_id
        self.session_column = SessionColumn(session_id)
        self.pillars = {}

    def compose(self) -> ComposeResult:
        yield Static(f"Session: {self.session_id}", classes="session-header")
        yield WorkflowStatusWidget(id=f"workflow-status-{self.session_id}")
        with VerticalScroll(id=f"scroll-{self.session_id}"):
            for node_id in self.session_column.pillars:
                widget = PillarWidget(node_id, id=f"pillar-{self.session_id}-{node_id}")
                self.pillars[node_id] = widget
                yield widget

    def update_data(self, events):
        """Updates the session data from events."""
        for event in events:
            node = event.get("node")
            etype = event.get("event_type")
            data = event.get("data")
            ts_str = event.get("timestamp")

            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str).timestamp()
                    if (
                        self.session_column.created_at == 0
                        or ts < self.session_column.created_at
                    ):
                        self.session_column.created_at = ts
                        if (
                            self.session_column.activated_at == 0
                            or ts < self.session_column.activated_at
                        ):
                            self.session_column.activated_at = ts
                except (ValueError, TypeError):
                    pass

            if node == "workflow" and etype == "workflow_status":
                self.session_column.workflow_status = data
                if data in ["success", "failed"] and ts_str:
                    try:
                        ts = datetime.fromisoformat(ts_str).timestamp()
                        self.session_column.completed_at = ts
                    except (ValueError, TypeError):
                        pass
            elif node and node != "workflow":
                pillar = self.session_column.get_pillar(node)
                if node not in self.pillars:
                    # New pillar discovered, add it to the UI
                    scroll = self.query_one(
                        f"#scroll-{self.session_id}", VerticalScroll
                    )
                    widget = PillarWidget(node, id=f"pillar-{self.session_id}-{node}")
                    self.pillars[node] = widget
                    scroll.mount(widget)

                if etype == "output":
                    for line in data.splitlines():
                        if line.strip():
                            pillar.add_line(line)
                elif etype == "status":
                    pillar.set_status(data, event.get("timestamp"))

        # Update workflow status widget
        status_widget = self.query_one(
            f"#workflow-status-{self.session_id}", WorkflowStatusWidget
        )
        status_widget.update_status(self.session_column.workflow_status)

        # Refresh all pillar widgets
        for node_id, pillar in self.session_column.pillars.items():
            if node_id in self.pillars:
                self.pillars[node_id].update_from_pillar(pillar)


class TextualDashboard(App):
    """The main Textual dashboard for visualizing multiple sessions."""

    CSS = """
    SessionWidget {
        width: 50;
        height: 100%;
        border: solid yellow;
        margin: 1;
    }

    SessionWidget:focus-within {
        border: double yellow;
    }

    .session-header {
        background: yellow;
        color: black;
        text-align: center;
        text-style: bold;
        height: 3;
        content-align: center middle;
    }

    WorkflowStatusWidget {
        height: 3;
        margin: 0 1;
    }

    PillarWidget {
        height: auto;
        min-height: 3;
        margin: 0;
        padding: 0;
    }

    #sessions-container {
        height: 1fr;
    }

    #stats-bar {
        background: $accent;
        color: white;
        height: 1;
        padding: 0 1;
    }

    #stats-bar.hidden {
        display: none;
    }

    Footer {
        height: 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("v", "toggle_stats", "Toggle Stats", show=True),
        Binding("tab", "next_session", "Next Session", show=True),
        Binding("shift+tab", "prev_session", "Prev Session", show=True),
        Binding("1", "switch_tmux(1)", "Tmux 1", show=False),
        Binding("2", "switch_tmux(2)", "Tmux 2", show=False),
        Binding("3", "switch_tmux(3)", "Tmux 3", show=False),
        Binding("4", "switch_tmux(4)", "Tmux 4", show=False),
        Binding("5", "switch_tmux(5)", "Tmux 5", show=False),
        Binding("6", "switch_tmux(6)", "Tmux 6", show=False),
        Binding("7", "switch_tmux(7)", "Tmux 7", show=False),
        Binding("8", "switch_tmux(8)", "Tmux 8", show=False),
        Binding("9", "switch_tmux(9)", "Tmux 9", show=False),
    ]

    def __init__(self, log_dir: Path | None = None, **kwargs):
        super().__init__(**kwargs)
        self.log_dir = log_dir or (Path.home() / ".copium" / "logs")
        self.log_offsets = {}
        self.session_widgets = {}
        self.codexbar_client = CodexbarClient()
        self.stats_strategies = [
            CodexStatsStrategy(self.codexbar_client),
            SystemStatsStrategy(),
        ]

    def compose(self) -> ComposeResult:
        yield Header()
        with HorizontalScroll(id="sessions-container"):
            # Sessions will be added here dynamically
            pass
        yield Static(id="stats-bar")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.0, self.update_from_logs)
        self.set_interval(2.0, self.update_footer_stats)
        self.update_from_logs()

    async def update_footer_stats(self) -> None:
        """Updates the stats bar with system/codex stats."""
        stats_parts = []
        for strategy in self.stats_strategies:
            if hasattr(strategy, "get_stats_async"):
                stats = await strategy.get_stats_async()
            else:
                stats = strategy.get_stats()

            if stats:
                if isinstance(stats, list):
                    for s in stats:
                        if isinstance(s, tuple):
                            stats_parts.append(Text(s[0], style=s[1]))
                        else:
                            stats_parts.append(Text(str(s)))
                else:
                    stats_parts.append(Text(str(stats)))
                stats_parts.append(Text(" | "))

        if stats_parts:
            # Remove trailing pipe
            if stats_parts[-1].plain == " | ":
                stats_parts.pop()

            full_stats = Text()
            for part in stats_parts:
                full_stats.append(part)

            self.query_one("#stats-bar", Static).update(full_stats)

    def get_sorted_session_ids(self) -> list[str]:
        """Returns session IDs sorted by status (running first) and then by time."""

        def sort_key(sid):
            widget = self.session_widgets.get(sid)
            if not widget:
                return (2, 0, sid)
            s = widget.session_column
            is_running = s.workflow_status == "running"
            if is_running:
                return (0, s.activated_at, sid)
            else:
                return (1, -s.completed_at, sid)

        return sorted(self.session_widgets.keys(), key=sort_key)

    def update_from_logs(self) -> None:
        """Reads .jsonl files and updates session states."""
        if not self.log_dir.exists():
            return

        log_files = sorted(self.log_dir.glob("*.jsonl"), key=os.path.getmtime)
        active_sids = {f.stem for f in log_files}

        container = self.query_one("#sessions-container")

        # Remove stale sessions
        for sid in list(self.session_widgets.keys()):
            if sid not in active_sids:
                self.session_widgets[sid].remove()
                del self.session_widgets[sid]
                if sid in self.log_offsets:
                    del self.log_offsets[sid]

        # Add or update sessions
        for target_file in log_files:
            sid = target_file.stem
            if sid not in self.session_widgets:
                widget = SessionWidget(sid, id=f"session-{sid}")
                self.session_widgets[sid] = widget
                container.mount(widget)

            offset = self.log_offsets.get(sid, 0)
            events = []
            try:
                with open(target_file) as f:
                    f.seek(offset)
                    for line in f:
                        try:
                            events.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
                    self.log_offsets[sid] = f.tell()

                if events:
                    self.session_widgets[sid].update_data(events)
            except Exception:
                pass

    def action_next_session(self) -> None:
        """Focus the next session widget."""
        sorted_sids = self.get_sorted_session_ids()
        if not sorted_sids:
            return

        current_focus = self.focused
        if (
            not current_focus
            or not any(isinstance(a, SessionWidget) for a in current_focus.ancestors_with_self)
        ):
            self.session_widgets[sorted_sids[0]].focus()
            return

        # Find which session widget is focused
        current_widget = next(
            a for a in current_focus.ancestors_with_self if isinstance(a, SessionWidget)
        )
        current_sid = current_widget.session_id

        try:
            idx = sorted_sids.index(current_sid)
            next_idx = (idx + 1) % len(sorted_sids)
            self.session_widgets[sorted_sids[next_idx]].focus()
        except ValueError:
            self.session_widgets[sorted_sids[0]].focus()

    def action_prev_session(self) -> None:
        """Focus the previous session widget."""
        sorted_sids = self.get_sorted_session_ids()
        if not sorted_sids:
            return

        current_focus = self.focused
        if (
            not current_focus
            or not any(isinstance(a, SessionWidget) for a in current_focus.ancestors_with_self)
        ):
            self.session_widgets[sorted_sids[-1]].focus()
            return

        current_widget = next(
            a for a in current_focus.ancestors_with_self if isinstance(a, SessionWidget)
        )
        current_sid = current_widget.session_id

        try:
            idx = sorted_sids.index(current_sid)
            prev_idx = (idx - 1) % len(sorted_sids)
            self.session_widgets[sorted_sids[prev_idx]].focus()
        except ValueError:
            self.session_widgets[sorted_sids[-1]].focus()

    def action_switch_tmux(self, index: int) -> None:
        """Switches to the tmux session at the given index."""
        sorted_sids = self.get_sorted_session_ids()
        if 0 < index <= len(sorted_sids):
            sid = sorted_sids[index - 1]
            from .tmux import switch_to_tmux_session

            switch_to_tmux_session(sid)

    def action_refresh(self) -> None:
        self.update_from_logs()

    def action_toggle_stats(self) -> None:
        """Toggles the visibility of the stats bar."""
        stats_bar = self.query_one("#stats-bar")
        stats_bar.toggle_class("hidden")
