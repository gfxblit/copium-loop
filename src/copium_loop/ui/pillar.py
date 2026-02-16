import time
from datetime import datetime

from rich import box
from rich.panel import Panel
from rich.text import Text

from .renderable import TailRenderable


class MatrixPillar:
    """Manages the buffer and rendering for a single agent phase."""

    # Statuses that indicate a node has completed execution (successfully or not)
    COMPLETION_STATUSES = frozenset(
        {
            "success",
            "approved",
            "failed",
            "rejected",
            "error",
            "pr_failed",
            "coded",
            "journaled",
            "no_lesson",
            "ok",
            "refactor",
        }
    )

    # Statuses that indicate a successful completion for visual styling
    SUCCESS_STATUSES = frozenset(
        {"success", "approved", "coded", "journaled", "no_lesson", "ok"}
    )

    # Statuses that indicate a failure for visual styling
    FAILURE_STATUSES = frozenset(
        {"error", "rejected", "failed", "pr_failed", "refactor"}
    )

    def __init__(self, name: str):
        self.name = name
        self.buffer = []
        self.status = "idle"
        self.max_buffer = 20
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
                elif self.start_time and status in self.COMPLETION_STATUSES:
                    self.duration = ts - self.start_time
                    self.completion_time = ts
            except (ValueError, TypeError):
                pass

    def get_header_text(self) -> Text:
        """Returns the header text for the pillar."""
        # Calculate display time if applicable - human readable (e.g. 1m 5s)
        time_suffix = ""
        duration_val = (
            self.duration
            if self.duration is not None
            else (
                int(time.time() - self.start_time)
                if self.start_time is not None and self.status == "active"
                else None
            )
        )

        if duration_val is not None:
            secs = int(duration_val)
            if secs >= 60:
                mins = secs // 60
                rem_secs = secs % 60
                time_suffix = (
                    f" [{mins}m {rem_secs}s]" if rem_secs > 0 else f" [{mins}m]"
                )
            else:
                time_suffix = f" [{secs}s]"

        # Add completion time for completed steps
        if self.completion_time is not None and self.status in self.COMPLETION_STATUSES:
            completion_dt = datetime.fromtimestamp(self.completion_time)
            completion_str = completion_dt.strftime("%H:%M:%S")
            time_suffix += f" @ {completion_str}"

        if self.status == "active":
            return Text(
                f"▶ {self.name.upper()}{time_suffix}", style="bold black on #00FF41"
            )
        elif self.status in self.SUCCESS_STATUSES:
            return Text(
                f"✔ {self.name.upper()}{time_suffix}", style="bold black on cyan"
            )
        elif self.status in self.FAILURE_STATUSES:
            return Text(
                f"✘ {self.name.upper()}{time_suffix}", style="bold white on red"
            )
        elif len(self.buffer) > 0:
            return Text(f"✔ {self.name.upper()}{time_suffix}", style="dim cyan")
        else:
            return Text(f"○ {self.name.upper()}", style="dim grey50")

    def get_content_renderable(self) -> TailRenderable:
        """Returns the content renderable for the pillar."""
        return TailRenderable(self.buffer, self.status)

    def render(self) -> Panel:
        # Visual Semantics:
        # active -> bright white header, pulsing
        # success/approved -> cyan checkmark
        # error/rejected/failed -> red X
        # idle with content -> grey checkmark (passed history)
        # idle without content -> dim grey (never run)

        header_text = self.get_header_text()

        if self.status == "active":
            border_style = "#00FF41"
        elif self.status in self.SUCCESS_STATUSES:
            border_style = "cyan"
        elif self.status in self.FAILURE_STATUSES:
            border_style = "red"
        else:
            border_style = "#666666"

        return Panel(
            self.get_content_renderable(),
            title=header_text,
            border_style=border_style,
            expand=True,
            box=box.HORIZONTALS,
        )
