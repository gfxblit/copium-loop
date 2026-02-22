import asyncio
import contextlib
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Label, Static

from ..gemini_stats import GeminiStatsClient
from .footer_stats import GeminiStatsStrategy
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
        height: auto;
        padding: 0 1;
        border-top: solid blue;
    }

    #stats-bar.hidden {
        display: none;
    }

    #empty-state-label {
        width: 100%;
        height: 100%;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("r", "refresh", "Refresh", show=True),
        Binding("v", "toggle_stats", "Toggle Stats", show=True),
        Binding("l", "toggle_system_logs", "Toggle Logs", show=True),
        Binding("tab", "next_page", "Next Page", show=True, priority=True),
        Binding("shift+tab", "prev_page", "Prev Page", show=True, priority=True),
        Binding("right", "next_page", "Next Page", show=False, priority=True),
        Binding("left", "prev_page", "Prev Page", show=False, priority=True),
        Binding("n", "next_page", "Next Page", show=False),
        Binding("p", "prev_page", "Prev Page", show=False),
        Binding("1", "switch_tmux(1)", "Tmux 1", show=False, priority=True),
        Binding("2", "switch_tmux(2)", "Tmux 2", show=False, priority=True),
        Binding("3", "switch_tmux(3)", "Tmux 3", show=False, priority=True),
        Binding("4", "switch_tmux(4)", "Tmux 4", show=False, priority=True),
        Binding("5", "switch_tmux(5)", "Tmux 5", show=False, priority=True),
        Binding("6", "switch_tmux(6)", "Tmux 6", show=False, priority=True),
        Binding("7", "switch_tmux(7)", "Tmux 7", show=False, priority=True),
        Binding("8", "switch_tmux(8)", "Tmux 8", show=False, priority=True),
        Binding("9", "switch_tmux(9)", "Tmux 9", show=False, priority=True),
    ]

    def __init__(
        self, log_dir: Path | None = None, enable_polling: bool = True, **kwargs
    ):
        super().__init__(**kwargs)
        self.log_dir = log_dir or (Path.home() / ".copium" / "logs")
        self.title = f"Copium Loop Monitor - {self.log_dir}"
        self.manager = SessionManager(self.log_dir)
        self.stats_client = GeminiStatsClient()
        self.stats_strategies = [
            GeminiStatsStrategy(self.stats_client),
        ]
        self._logs_lock = asyncio.Lock()
        self._stats_lock = asyncio.Lock()

        self._ui_lock = asyncio.Lock()
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
        if self._stats_lock.locked():
            return
        async with self._stats_lock:
            try:
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

                if stats_parts and stats_parts[-1].plain == " | ":
                    # Remove trailing pipe
                    stats_parts.pop()

                full_stats = Text()
                for part in stats_parts:
                    full_stats.append(part)

                # Add pagination info
                _, page, total = self.manager.get_visible_sessions()
                if total > 1:
                    if stats_parts:
                        full_stats.append(Text(" | "))
                    full_stats.append(Text(f"Page {page}/{total}", style="bold yellow"))

                if full_stats:
                    with contextlib.suppress(Exception):
                        self.query_one("#stats-bar", Static).update(full_stats)
                else:
                    with contextlib.suppress(Exception):
                        self.query_one("#stats-bar", Static).update("")
            except Exception:
                pass

    async def update_from_logs(self) -> None:
        """Reads logs and updates the UI."""
        if self._logs_lock.locked():
            return
        async with self._logs_lock:
            try:
                await asyncio.to_thread(self.manager.update_from_logs)
                await self.update_ui()
            except Exception:
                pass

    async def update_ui(self) -> None:
        """Syncs the UI with the session manager's state."""
        async with self._ui_lock:
            container = self.query_one("#sessions-container", Horizontal)
            visible_sessions, _, _ = self.manager.get_visible_sessions()
            visible_sids = [s.session_id for s in visible_sessions]

            current_widgets = list(container.query(SessionWidget))
            current_sids = [w.session_id for w in current_widgets]

            if not visible_sessions:
                if not container.query("#empty-state-label"):
                    await container.remove_children()
                    await container.mount(
                        Label(
                            "No active sessions found.\nWaiting for workflow to start...",
                            id="empty-state-label",
                        )
                    )
                return

            # If we have sessions, ensure empty state is gone
            has_empty_label = bool(container.query("#empty-state-label"))

            if current_sids == visible_sids and not has_empty_label:
                # Just refresh existing
                for i, widget in enumerate(current_widgets, 1):
                    widget.index = i
                    await widget.refresh_ui()
            else:
                # Rebuild
                await container.remove_children()
                import re

                for i, session in enumerate(visible_sessions, 1):
                    safe_sid = re.sub(r"[^a-zA-Z0-9_\-]", "_", session.session_id)
                    w = SessionWidget(session, index=i, id=f"session-{safe_sid}")
                    await container.mount(w)
                    await w.refresh_ui()

    async def action_next_page(self) -> None:
        self.manager.next_page()
        await self.update_ui()
        await self.update_footer_stats()

    async def action_prev_page(self) -> None:
        self.manager.prev_page()
        await self.update_ui()
        await self.update_footer_stats()

    def action_switch_tmux(self, index: int) -> None:
        """Switches to the tmux session at the given index (1-based)."""
        # Get visible sessions to map index to session ID on the current page
        visible_sessions, _, _ = self.manager.get_visible_sessions()
        if 0 < index <= len(visible_sessions):
            sid = visible_sessions[index - 1].session_id
            from .tmux import extract_tmux_session, switch_to_tmux_session

            target = extract_tmux_session(sid)
            if target:
                switch_to_tmux_session(target)

    async def action_refresh(self) -> None:
        await self.update_from_logs()

    def action_toggle_stats(self) -> None:
        self.query_one("#stats-bar").toggle_class("hidden")

    async def action_toggle_system_logs(self) -> None:
        self.manager.toggle_system_logs()
        await self.update_ui()
