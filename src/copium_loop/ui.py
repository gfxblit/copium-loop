import json
import os
import select
import subprocess
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
from rich.style import Style
from rich.text import Text


class TailRenderable:
    """A custom Rich renderable that handles height-constrained rendering (clipping from the top)."""

    def __init__(self, buffer: list[str], status: str):
        self.buffer = buffer
        self.status = status

    def __rich_console__(self, console, options):
        # Use provided height/width or console defaults
        height = options.max_height if options.max_height is not None else console.height
        width = options.max_width if options.max_width is not None else console.width

        rendered_lines = []

        # Iterate backwards through the buffer to find the lines that fit from the bottom
        for i, line in enumerate(reversed(self.buffer)):
            # distance_from_end: 0 is newest
            distance_from_end = i

            if distance_from_end == 0:
                style = Style(color="#FFFFFF", bold=True)
                prefix = "> "
            elif distance_from_end < 10:
                # Recent lines: Neon Green
                style = Style(color="#00FF41")
                prefix = "  "
            elif distance_from_end == 2:
                # History: Dark Green
                style = Style(color="#008F11")
                prefix = "  "
            else:
                # Older: Fade to Grey/Black
                style = Style(color="#333333")
                prefix = "  "

            text = Text(f"{prefix}{line}", style=style)
            # Wrap the text to the available width
            # This returns a list of Text objects, one for each console line
            lines = text.wrap(console, width)

            # Since we are going backwards, we want to add these lines to the START
            # of our rendered_lines list. The wrapped lines for THIS buffer line
            # should stay in their original relative order.
            for wrapped_line in reversed(lines):
                rendered_lines.insert(0, wrapped_line)
                if len(rendered_lines) >= height:
                    break

            if len(rendered_lines) >= height:
                break

        yield from rendered_lines


class MatrixPillar:
    """Manages the buffer and rendering for a single agent phase."""

    def __init__(self, name: str):
        self.name = name
        self.buffer = []
        self.status = "idle"
        self.max_buffer = 10
        self.last_update = time.time()
        self.start_time = None
        self.duration = None
        self.completion_time = None

    def add_line(self, line: str):
        self.buffer.append(line)
        if len(self.buffer) > self.max_buffer:
            self.buffer.pop(0)
        self.last_update = time.time()

    def set_status(self, status: str, timestamp_str: str | None = None):
        self.status = status
        if timestamp_str:
            try:
                # Parse ISO format timestamp
                ts = datetime.fromisoformat(timestamp_str).timestamp()
                if status == "active":
                    self.start_time = ts
                    self.duration = None
                    self.completion_time = None
                elif self.start_time and status in ["success", "approved", "failed", "rejected", "error", "pr_failed", "coded"]:
                    self.duration = ts - self.start_time
                    self.completion_time = ts
            except (ValueError, TypeError):
                pass

    def render(self) -> Panel:
        # Visual Semantics:
        # active -> bright white header, pulsing
        # success/approved -> cyan checkmark
        # error/rejected/failed -> red X
        # idle with content -> grey checkmark (passed history)
        # idle without content -> dim grey (never run)

        has_content = len(self.buffer) > 0

        # Calculate display time if applicable - human readable (e.g. 1m 5s)
        time_suffix = ""
        duration_val = self.duration if self.duration is not None else (
            int(time.time() - self.start_time) if self.start_time is not None and self.status == "active" else None
        )

        if duration_val is not None:
            secs = int(duration_val)
            if secs >= 60:
                mins = secs // 60
                rem_secs = secs % 60
                time_suffix = f" [{mins}m {rem_secs}s]" if rem_secs > 0 else f" [{mins}m]"
            else:
                time_suffix = f" [{secs}s]"

        # Add completion time for completed steps
        if self.completion_time is not None and self.status in ["success", "approved", "failed", "rejected", "error", "pr_failed", "coded"]:
            completion_dt = datetime.fromtimestamp(self.completion_time)
            completion_str = completion_dt.strftime("%H:%M:%S")
            time_suffix += f" @ {completion_str}"

        if self.status == "active":
            header_text = Text(f"▶ {self.name.upper()}{time_suffix}", style="bold black on #00FF41")
            border_style = "#00FF41"
        elif self.status in ["success", "approved", "coded"]:
            header_text = Text(f"✔ {self.name.upper()}{time_suffix}", style="bold black on cyan")
            border_style = "cyan"
        elif self.status in ["error", "rejected", "failed", "pr_failed"]:
            header_text = Text(f"✘ {self.name.upper()}{time_suffix}", style="bold white on red")
            border_style = "red"
        elif has_content:
            header_text = Text(f"✔ {self.name.upper()}{time_suffix}", style="dim cyan")
            border_style = "grey37"
        else:
            header_text = Text(f"○ {self.name.upper()}", style="dim grey50")
            border_style = "grey37"

        return Panel(
            TailRenderable(self.buffer, self.status),
            title=header_text,
            border_style=border_style,
            expand=True,
        )


class SessionColumn:
    """Represents a vertical session column containing stacked agent phases."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.workflow_status = "running"  # Track workflow-level status
        self.pillars = {
            "coder": MatrixPillar("Coder"),
            "tester": MatrixPillar("Tester"),
            "reviewer": MatrixPillar("Reviewer"),
            "pr_creator": MatrixPillar("PR Creator"),
        }

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
                weight += 10  # Ensure active node has enough space
            elif pillar.status == "idle" and count == 0:
                weight = 1  # Keep empty idle nodes very small

            ratios[node] = weight

        # Add workflow status banner if workflow has completed
        if self.workflow_status in ["success", "failed"]:
            col_layout.split_column(
                Layout(name="header", size=3),
                Layout(name="workflow_status", size=3),
                Layout(name="coder", ratio=ratios["coder"]),
                Layout(name="tester", ratio=ratios["tester"]),
                Layout(name="reviewer", ratio=ratios["reviewer"]),
                Layout(name="pr_creator", ratio=ratios["pr_creator"]),
            )

            # Render workflow status banner
            if self.workflow_status == "failed":
                status_text = Text("⚠ WORKFLOW FAILED - MAX RETRIES EXCEEDED", style="bold white on red", justify="center")
                col_layout["workflow_status"].update(Panel(status_text, border_style="red"))
            else:  # success
                status_text = Text("✓ WORKFLOW COMPLETED SUCCESSFULLY", style="bold black on green", justify="center")
                col_layout["workflow_status"].update(Panel(status_text, border_style="green"))
        else:
            col_layout.split_column(
                Layout(name="header", size=3),
                Layout(name="coder", ratio=ratios["coder"]),
                Layout(name="tester", ratio=ratios["tester"]),
                Layout(name="reviewer", ratio=ratios["reviewer"]),
                Layout(name="pr_creator", ratio=ratios["pr_creator"]),
            )

        # Dynamically truncate session_id based on available column width
        if column_width:
            # Account for: panel borders (2), padding (2)
            available_width = column_width - 4
            header_text = self.session_id[:available_width]
        else:
            header_text = self.session_id

        col_layout["header"].update(
            Panel(Text(header_text, justify="center", style="bold yellow"), border_style="yellow")
        )
        for node, pillar in self.pillars.items():
            col_layout[node].update(pillar.render())

        return col_layout


class Dashboard:
    """The main Rich dashboard for visualizing multiple sessions side-by-side."""

    def __init__(self):
        self.console = Console()
        self.sessions = {}  # session_id -> SessionColumn
        self.log_dir = Path.home() / ".copium" / "logs"
        self.log_offsets = {}
        self.current_page = 0
        self.sessions_per_page = 4

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="main"),
            Layout(name="footer", size=3),
        )

        # Pagination logic - newest sessions first
        session_list = list(self.sessions.values())[::-1]
        num_sessions = len(session_list)
        num_pages = (num_sessions + self.sessions_per_page - 1) // self.sessions_per_page if num_sessions > 0 else 1

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
            layout["main"].split_row(*[
                Layout(s.render(column_width=column_width))
                for s in active_sessions
            ])
        else:
            layout["main"].update(Panel(Text("WAITING FOR SESSIONS...", justify="center", style="dim")))

        layout["footer"].update(self.make_footer())
        return layout

    def make_footer(self) -> Panel:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        spark = "".join(["█" if i < cpu / 10 else " " for i in range(10)])

        num_sessions = len(self.sessions)
        num_pages = (num_sessions + self.sessions_per_page - 1) // self.sessions_per_page if num_sessions > 0 else 1

        pagination_info = f"PAGE {self.current_page + 1}/{num_pages} [TAB/ARROWS to navigate]" if num_sessions > 0 else ""

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

    def extract_tmux_session(self, session_id: str) -> str | None:
        """Extracts the tmux session name from a session_id.

        Session IDs are formatted as {tmux_session}, {tmux_session}_{pane}
        or session_{timestamp}.
        Returns the tmux session name if it exists, None otherwise.
        """
        # Handle non-tmux sessions (format: session_{timestamp})
        if session_id.startswith("session_"):
            return None

        # Handle old format: {tmux_session}_{pane}
        # We check if it ends with _%digit or _digit
        if "_" in session_id:
            parts = session_id.rsplit("_", 1)
            suffix = parts[1]
            if suffix.startswith("%") or suffix.isdigit():
                return parts[0]

        # Otherwise, the session_id is the tmux session name
        return session_id

    def switch_to_tmux_session(self, session_name: str):
        """Switches the current tmux client to the specified session."""
        # Check if we're running inside tmux
        if not os.environ.get("TMUX"):
            return  # Not in tmux, silently ignore

        try:
            subprocess.run(
                ["tmux", "switch-client", "-t", "--", session_name],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            # Session doesn't exist or other error, silently ignore
            pass
        except Exception:
            # Any other error, silently ignore
            pass

    def update_from_logs(self):
        """Reads .jsonl files and updates session states."""
        log_files = sorted(self.log_dir.glob("*.jsonl"), key=os.path.getmtime)

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

                            # Handle workflow-level status events
                            if node == "workflow" and etype == "workflow_status":
                                self.sessions[sid].workflow_status = data
                            elif node in self.sessions[sid].pillars:
                                if etype == "output":
                                    for line in data.splitlines():
                                        if line.strip():
                                            self.sessions[sid].pillars[node].add_line(line)
                                elif etype == "status":
                                    self.sessions[sid].pillars[node].set_status(data, event.get("timestamp"))
                        except json.JSONDecodeError:
                            continue
                    self.log_offsets[sid] = f.tell()
            except Exception:
                pass

    def run_monitor(self, _session_id: str | None = None):
        """Runs the live dashboard."""
        self.current_page = 0

        # Save terminal settings to restore them later
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            with Live(self.make_layout(), console=self.console, screen=True, refresh_per_second=4) as live:
                while True:
                    self.update_from_logs()

                    # Check for keyboard input (non-blocking with longer timeout for better responsiveness)
                    if select.select([sys.stdin], [], [], 0.05)[0]:
                        key = sys.stdin.read(1)

                        # Handle Escape sequences (Arrows, etc.)
                        if key == "\x1b" and select.select([sys.stdin], [], [], 0.05)[0]:
                            # Read the next two characters if available
                            key += sys.stdin.read(2)

                        num_sessions = len(self.sessions)
                        num_pages = (num_sessions + self.sessions_per_page - 1) // self.sessions_per_page if num_sessions > 0 else 1

                        if key in ["\t", "\x1b[C"]:  # Tab or Right Arrow
                            self.current_page = (self.current_page + 1) % num_pages
                        elif key in ["\x1b[D", "\x1b[Z"]:  # Left Arrow or Shift+Tab
                            self.current_page = (self.current_page - 1) % num_pages
                        elif key.lower() == "q":
                            break
                        elif key.isdigit() and key != "0":  # Number keys 1-9
                            session_num = int(key)
                            # Get the session list for the current page
                            session_list = list(self.sessions.values())[::-1]
                            start_idx = self.current_page * self.sessions_per_page
                            end_idx = start_idx + self.sessions_per_page
                            active_sessions = session_list[start_idx:end_idx]

                            # Check if the session number is valid for current page
                            if 1 <= session_num <= len(active_sessions):
                                target_session = active_sessions[session_num - 1]
                                tmux_session = self.extract_tmux_session(target_session.session_id)
                                if tmux_session:
                                    self.switch_to_tmux_session(tmux_session)

                    live.update(self.make_layout())
                    time.sleep(0.05)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
