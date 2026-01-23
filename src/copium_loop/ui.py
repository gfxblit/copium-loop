import json
import os
import time
from datetime import datetime
from pathlib import Path

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

    def add_line(self, line: str):
        self.buffer.append(line)
        if len(self.buffer) > self.max_buffer:
            self.buffer.pop(0)
        self.last_update = time.time()

    def set_status(self, status: str):
        self.status = status

    def render(self) -> Panel:
        pulse = int(time.time() * 2) % 2 == 0
        if self.status == "active":
            header_text = Text(f"▶ {self.name.upper()}", style="bold bright_white on #00FF41")
        elif self.status == "success":
            header_text = Text(f"✔ {self.name.upper()}", style="bold black on cyan")
        elif self.status == "error":
            header_text = Text(f"✘ {self.name.upper()}", style="bold white on red")
        else:
            header_text = Text(f"○ {self.name.upper()}", style="dim grey50")

        content = Text()
        # Waterfall effect: newest lines at the top
        for i, line in enumerate(reversed(self.buffer)):
            if i == 0:
                # Newest line: Bright White
                style = Style(color="#FFFFFF", bold=True)
                prefix = "> " if self.status == "active" else "  "
                content.append(f"{prefix}{line}\n", style=style)
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
            border_style="#00FF41" if self.status == "active" else "grey37",
            expand=True,
        )


class SessionColumn:
    """Represents a vertical session column containing stacked agent phases."""

    def __init__(self, session_id: str):
        self.session_id = session_id
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

    def make_layout(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="main"),
            Layout(name="footer", size=3),
        )
        
        # Display up to 4 sessions side-by-side
        active_sessions = list(self.sessions.values())[-4:]
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
        
        footer_text = Text.assemble(
            (" COPIUM MULTI-MONITOR ", "bold white on blue"),
            f"  SESSIONS: {len(self.sessions)}  ",
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

                            if node in self.sessions[sid].pillars:
                                if etype == "output":
                                    for l in data.splitlines():
                                        if l.strip():
                                            self.sessions[sid].pillars[node].add_line(l)
                                elif etype == "status":
                                    self.sessions[sid].pillars[node].set_status(data)
                        except json.JSONDecodeError:
                            continue
                    self.log_offsets[sid] = f.tell()
            except Exception:
                pass

    def run_monitor(self, session_id: str | None = None):
        """Runs the live dashboard."""
        with Live(self.make_layout(), console=self.console, screen=True, refresh_per_second=4) as live:
            while True:
                self.update_from_logs()
                live.update(self.make_layout())
                time.sleep(0.25)

    def make_footer(self) -> Panel:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        spark = "".join(["█" if i < cpu / 10 else " " for i in range(10)])
        
        footer_text = Text.assemble(
            (" ACTIVE SESSIONS: ", "bold white on blue"),
            (f" {len(self.sessions)} ", "bold yellow on blue"),
            "  ",
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

                            if node in self.sessions[sid].pillars:
                                if etype == "output":
                                    for l in data.splitlines():
                                        if l.strip():
                                            self.sessions[sid].pillars[node].add_line(l)
                                elif etype == "status":
                                    self.sessions[sid].pillars[node].set_status(data)
                        except json.JSONDecodeError:
                            continue
                    self.log_offsets[sid] = f.tell()
            except Exception:
                pass

    def run_monitor(self, session_id: str | None = None):
        """Runs the live dashboard."""
        with Live(self.make_layout(), console=self.console, screen=True, refresh_per_second=4) as live:
            while True:
                self.update_from_logs()
                live.update(self.make_layout())
                time.sleep(0.25)
