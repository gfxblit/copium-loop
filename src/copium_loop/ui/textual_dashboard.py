import contextlib
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Static

from ..codexbar import CodexbarClient
from .footer_stats import CodexStatsStrategy, SystemStatsStrategy
from .manager import SessionManager
from .widgets.session import SessionWidget


class TextualDashboard(App):
    """The main Textual dashboard for visualizing multiple sessions."""

    CSS = """
    #sessions-container {
        height: 1fr;
        align: center middle;
    }

    #stats-bar {
        background: $surface;
        color: white;
        height: 2;
        padding: 0 1;
        border-top: solid blue;
    }

    #stats-bar.hidden {
        display: none;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("v", "toggle_stats", "Toggle Stats", show=True),
        Binding("tab", "next_page", "Next Page", show=True),
        Binding("shift+tab", "prev_page", "Prev Page", show=True),
        Binding("right", "next_session", "Focus Next", show=False),
        Binding("left", "prev_session", "Focus Prev", show=False),
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

    def __init__(
        self, log_dir: Path | None = None, enable_polling: bool = True, **kwargs
    ):
        super().__init__(**kwargs)
        self.log_dir = log_dir or (Path.home() / ".copium" / "logs")
        self.title = f"Copium Loop Monitor - {self.log_dir}"
        self.manager = SessionManager(self.log_dir)
        self.codexbar_client = CodexbarClient()
        self.stats_strategies = [
            CodexStatsStrategy(self.codexbar_client),
            SystemStatsStrategy(),
        ]
        self._updating = False
        self.enable_polling = enable_polling

    def compose(self) -> ComposeResult:
        yield Horizontal(id="sessions-container")
        yield Static(id="stats-bar")

    def on_mount(self) -> None:
        if self.enable_polling:
            self.set_interval(1.0, self.update_from_logs)
            self.set_interval(2.0, self.update_footer_stats)
            self.run_worker(self.update_from_logs())
            self.run_worker(self.update_footer_stats())

    async def update_footer_stats(self) -> None:
        """Updates the stats bar with system/codex stats."""
        stats_parts = []
        for strategy in self.stats_strategies:
            try:
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
            except Exception:
                pass

        if stats_parts:
            # Remove trailing pipe
            if stats_parts[-1].plain == " | ":
                stats_parts.pop()

            full_stats = Text()
            for part in stats_parts:
                full_stats.append(part)

            # Add pagination info
            _, page, total = self.manager.get_visible_sessions()
            if total > 1:
                full_stats.append(Text(f" | Page {page}/{total}", style="bold yellow"))

            with contextlib.suppress(Exception):
                self.query_one("#stats-bar", Static).update(full_stats)

    async def update_from_logs(self) -> None:
        """Reads logs and updates the UI."""
        if self._updating:
            return
        self._updating = True
        try:
            self.manager.update_from_logs()
            await self.update_ui()
        finally:
            self._updating = False

    async def update_ui(self) -> None:
        """Syncs the UI with the session manager's state."""
        container = self.query_one("#sessions-container", Horizontal)
        visible_sessions, _, _ = self.manager.get_visible_sessions()
        visible_sids = [s.session_id for s in visible_sessions]

        current_sids = [w.session_id for w in container.query(SessionWidget)]

        if current_sids == visible_sids:
            # Just refresh existing
            existing_widgets = {w.session_id: w for w in container.query(SessionWidget)}
            for session in visible_sessions:
                await existing_widgets[session.session_id].refresh_ui()
        else:
            # Rebuild
            await container.remove_children()
            for session in visible_sessions:
                w = SessionWidget(session, id=f"session-{session.session_id}")
                await container.mount(w)
                # w.refresh_ui() is called in w.on_mount(), which runs after mount

    async def action_next_page(self) -> None:
        self.manager.next_page()
        await self.update_ui()

    async def action_prev_page(self) -> None:
        self.manager.prev_page()
        await self.update_ui()

    def action_next_session(self) -> None:
        self.screen.focus_next()

    def action_prev_session(self) -> None:
        self.screen.focus_previous()

    def action_switch_tmux(self, index: int) -> None:
        """Switches to the tmux session at the given index (1-based)."""
        # Get all sorted sessions to map index to session ID, regardless of page
        sorted_sessions = self.manager.get_sorted_sessions()
        if 0 < index <= len(sorted_sessions):
            sid = sorted_sessions[index - 1].session_id
            from .tmux import switch_to_tmux_session

            switch_to_tmux_session(sid)

    async def action_refresh(self) -> None:
        await self.update_from_logs()

    def action_toggle_stats(self) -> None:
        self.query_one("#stats-bar").toggle_class("hidden")
