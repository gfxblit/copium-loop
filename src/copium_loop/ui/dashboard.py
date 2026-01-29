import json
import os
import sys
import termios
import time
import tty
from datetime import datetime
from pathlib import Path

import psutil
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

from ..input_reader import InputReader
from .column import SessionColumn
from .tmux import extract_tmux_session, switch_to_tmux_session


class Dashboard:
    """The main Rich dashboard for visualizing multiple sessions side-by-side."""

    def __init__(self):
        self.console = Console()
        self.sessions = {}  # session_id -> SessionColumn
        self.log_dir = Path.home() / ".copium" / "logs"
        self.log_offsets = {}
        self.current_page = 0
        self.sessions_per_page = 3

    def get_sorted_sessions(self) -> list[SessionColumn]:
        """Returns sessions sorted by status (running first) and then by activation/completion time."""

        def sort_key(s):
            is_running = s.workflow_status == "running"
            if is_running:
                # Group 0: Running sessions, sorted by activation time (oldest first)
                return (0, s.activated_at, s.session_id)
            else:
                # Group 1: Completed sessions, sorted by completion time (newest first)
                # We use negative timestamp to get newest first in an ascending sort
                return (1, -s.completed_at, s.session_id)

        return sorted(self.sessions.values(), key=sort_key)

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        # Pagination logic - sort by running status and creation order
        session_list = self.get_sorted_sessions()
        num_sessions = len(session_list)
        num_pages = (
            (num_sessions + self.sessions_per_page - 1) // self.sessions_per_page
            if num_sessions > 0
            else 1
        )

        # Ensure current_page is valid
        self.current_page = max(0, min(self.current_page, num_pages - 1))

        start_idx = self.current_page * self.sessions_per_page
        end_idx = start_idx + self.sessions_per_page
        active_sessions = session_list[start_idx:end_idx]

        if active_sessions:
            # Calculate column width based on console width
            num_columns = len(active_sessions)
            # Account for borders between columns (1 char per border)
            column_width = (self.console.width - num_columns + 1) // num_columns

            # Pass column width to each session for display
            layout["main"].split_row(
                *[Layout(s.render(column_width=column_width)) for s in active_sessions]
            )
        else:
            layout["main"].update(
                Panel(Text("WAITING FOR SESSIONS...", justify="center", style="dim"))
            )

        layout["footer"].update(self.make_footer())
        return layout

    def make_footer(self) -> Panel:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        spark = "".join(["█" if i < cpu / 10 else " " for i in range(10)])

        num_sessions = len(self.sessions)
        num_pages = (
            (num_sessions + self.sessions_per_page - 1) // self.sessions_per_page
            if num_sessions > 0
            else 1
        )

        pagination_info = (
            f"PAGE {self.current_page + 1}/{num_pages} [TAB/ARROWS to navigate]"
            if num_sessions > 0
            else ""
        )

        footer_text = Text.assemble(
            (" COPIUM MULTI-MONITOR ", "bold white on blue"),
            f"  SESSIONS: {num_sessions}  ",
            (f"  {pagination_info}  ", "bold yellow"),
            (f"CPU: {cpu}%", "bright_green"),
            f" [{spark}] ",
            "  ",
            (f"MEM: {mem}%", "bright_cyan"),
        )
        return Panel(footer_text, border_style="blue")

    def update_from_logs(self):
        """Reads .jsonl files and updates session states."""
        log_files = sorted(self.log_dir.glob("*.jsonl"), key=os.path.getmtime)
        active_sids = {f.stem for f in log_files}

        # Remove stale sessions
        stale_sids = [sid for sid in self.sessions if sid not in active_sids]
        for sid in stale_sids:
            del self.sessions[sid]
            if sid in self.log_offsets:
                del self.log_offsets[sid]

        for target_file in log_files:
            sid = target_file.stem
            if sid not in self.sessions:
                self.sessions[sid] = SessionColumn(sid)

            offset = self.log_offsets.get(sid, 0)
            try:
                with open(target_file) as f:
                    f.seek(offset)
                    for line in f:
                        try:
                            event = json.loads(line)
                            node = event.get("node")
                            etype = event.get("event_type")
                            data = event.get("data")
                            ts_str = event.get("timestamp")

                            # Use the first event's timestamp as the creation time
                            if ts_str:
                                try:
                                    ts = datetime.fromisoformat(ts_str).timestamp()
                                    # Only set if it's the first time or earlier than current
                                    if (
                                        self.sessions[sid].created_at == 0
                                        or ts < self.sessions[sid].created_at
                                    ):
                                        self.sessions[sid].created_at = ts
                                        # Also initialize activated_at to the first evidence of life
                                        if (
                                            self.sessions[sid].activated_at == 0
                                            or ts < self.sessions[sid].activated_at
                                        ):
                                            self.sessions[sid].activated_at = ts
                                except (ValueError, TypeError):
                                    pass

                            # Handle workflow-level status events
                            if node == "workflow" and etype == "workflow_status":
                                self.sessions[sid].workflow_status = data
                                # If it just finished in the log, update completed_at from the log timestamp
                                if data in ["success", "failed"] and ts_str:
                                    try:
                                        ts = datetime.fromisoformat(ts_str).timestamp()
                                        self.sessions[sid].completed_at = ts
                                    except (ValueError, TypeError):
                                        pass
                            elif node in self.sessions[sid].pillars:
                                if etype == "output":
                                    for line in data.splitlines():
                                        if line.strip():
                                            self.sessions[sid].pillars[node].add_line(
                                                line
                                            )
                                elif etype == "status":
                                    self.sessions[sid].pillars[node].set_status(
                                        data, event.get("timestamp")
                                    )
                        except json.JSONDecodeError:
                            continue
                    self.log_offsets[sid] = f.tell()
            except Exception as e:
                print(f"Error processing log file {target_file}: {e}", file=sys.stderr)

    def run_monitor(self, _session_id: str | None = None):
        """Runs the live dashboard."""
        self.current_page = 0
        input_reader = InputReader()

        # Save terminal settings to restore them later
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            with Live(
                self.make_layout(),
                console=self.console,
                screen=True,
                refresh_per_second=4,
            ) as live:
                while True:
                    self.update_from_logs()

                    # Check for keyboard input using the new robust InputReader
                    key = input_reader.get_key(timeout=0.05)

                    if key:
                        num_sessions = len(self.sessions)
                        num_pages = (
                            (num_sessions + self.sessions_per_page - 1)
                            // self.sessions_per_page
                            if num_sessions > 0
                            else 1
                        )

                        if key in ["\t", "\x1b[C"]:  # Tab or Right Arrow
                            self.current_page = (self.current_page + 1) % num_pages
                        elif key in ["\x1b[D", "\x1b[Z"]:  # Left Arrow or Shift+Tab
                            self.current_page = (self.current_page - 1) % num_pages
                        elif key.lower() == "q":
                            break
                        elif key.lower() == "r":
                            # Manual refresh - update all logs immediately
                            self.update_from_logs()
                        elif key.isdigit() and key != "0":  # Number keys 1-9
                            session_num = int(key)
                            # Get the session list for the current page
                            session_list = self.get_sorted_sessions()
                            start_idx = self.current_page * self.sessions_per_page
                            end_idx = start_idx + self.sessions_per_page
                            active_sessions = session_list[start_idx:end_idx]

                            # Check if the session number is valid for current page
                            if 1 <= session_num <= len(active_sessions):
                                target_session = active_sessions[session_num - 1]
                                tmux_session = extract_tmux_session(
                                    target_session.session_id
                                )
                                if tmux_session:
                                    switch_to_tmux_session(tmux_session)

                    live.update(self.make_layout())
                    time.sleep(0.05)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
