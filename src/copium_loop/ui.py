import json
import os
import time
from datetime import datetime
from pathlib import Path

import select
import sys
import termios
import tty

import psutil
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.text import Text
from rich.style import Style


class MatrixPillar:
    """Manages the buffer and rendering for a single agent phase."""

    def __init__(self, name: str):
        self.name = name
        self.buffer = []
        self.status = "idle"
        self.max_buffer = 100
        self.last_update = time.time()
        self.start_time = None
        self.duration = None

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
                elif self.start_time and status in ["success", "approved", "failed", "rejected", "error", "pr_failed", "coded"]:
                    self.duration = ts - self.start_time
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
        
        # Calculate display time if applicable
        time_suffix = ""
        if self.duration is not None:
            time_suffix = f" [{int(self.duration)}s]"
        elif self.start_time is not None and self.status == "active":
            elapsed = int(time.time() - self.start_time)
            time_suffix = f" [{elapsed}s]"

        if self.status == "active":
            header_text = Text(f"▶ {self.name.upper()}{time_suffix}", style="bold bright_white on #00FF41")
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

        content = Text()
        # Waterfall effect: newest lines at the top
        for i, line in enumerate(reversed(self.buffer)):
            if i == 0 and self.status == "active":
                # Newest line while active: Bright White
                style = Style(color="#FFFFFF", bold=True)
                content.append(f"> {line}\n", style=style)
            elif i < 5:
                # Active Context: Neon Green
                style = Style(color="#00FF41")
                content.append(f"  {line}\n", style=style)
            elif i < 15:
                # History: Dark Green
                style = Style(color="#008F11")
                content.append(f"  {line}\n", style=style)
            else:
                # Older: Fade to Grey/Black
                style = Style(color="#333333")
                content.append(f"  {line}\n", style=style)

        return Panel(
            content,
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

    def render(self) -> Layout:
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
        
        col_layout["header"].update(
            Panel(Text(self.session_id, justify="center", style="bold yellow"), border_style="yellow")
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
            layout["main"].split_row(*[Layout(s.render()) for s in active_sessions])
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

    def update_from_logs(self):
        """Reads .jsonl files and updates session states."""
        log_files = sorted(self.log_dir.glob("*.jsonl"), key=os.path.getmtime)
        
        for target_file in log_files:
            sid = target_file.stem
            if sid not in self.sessions:
                self.sessions[sid] = SessionColumn(sid)
            
            offset = self.log_offsets.get(sid, 0)
            try:
                with open(target_file, "r") as f:
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
                                    for l in data.splitlines():
                                        if l.strip():
                                            self.sessions[sid].pillars[node].add_line(l)
                                elif etype == "status":
                                    self.sessions[sid].pillars[node].set_status(data, event.get("timestamp"))
                        except json.JSONDecodeError:
                            continue
                    self.log_offsets[sid] = f.tell()
            except Exception:
                pass

    def run_monitor(self, session_id: str | None = None):
        """Runs the live dashboard."""
        self.current_page = 0
        
        # Save terminal settings to restore them later
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setcbreak(sys.stdin.fileno())
            with Live(self.make_layout(), console=self.console, screen=True, refresh_per_second=4) as live:
                while True:
                    self.update_from_logs()
                    
                    # Check for keyboard input (non-blocking)
                    if select.select([sys.stdin], [], [], 0)[0]:
                        key = sys.stdin.read(1)
                        
                        # Handle Escape sequences (Arrows, etc.)
                        if key == "\x1b":
                            # Read the next two characters if available
                            if select.select([sys.stdin], [], [], 0.05)[0]:
                                key += sys.stdin.read(2)
                        
                        num_sessions = len(self.sessions)
                        num_pages = (num_sessions + self.sessions_per_page - 1) // self.sessions_per_page if num_sessions > 0 else 1
                        
                        if key in ["\t", "\x1b[C"]:  # Tab or Right Arrow
                            self.current_page = (self.current_page + 1) % num_pages
                        elif key in ["\x1b[D", "\x1b[Z"]:  # Left Arrow or Shift+Tab
                            self.current_page = (self.current_page - 1) % num_pages
                        elif key.lower() == "q":
                            break
                    
                    live.update(self.make_layout())
                    time.sleep(0.1)
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
