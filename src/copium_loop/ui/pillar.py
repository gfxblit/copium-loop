import time
from datetime import datetime

from rich import box
from rich.panel import Panel
from rich.text import Text

from .renderable import TailRenderable

# Pillar Status Colors
PILLAR_COLOR_ACTIVE = "#00FF41"
PILLAR_COLOR_SUCCESS = "cyan"
PILLAR_COLOR_FAILURE = "red"
PILLAR_COLOR_DEFAULT = "#666666"
PILLAR_COLOR_IDLE_TEXT = "dim grey50"
PILLAR_COLOR_IDLE_WITH_CONTENT = "dim cyan"

# Pillar Icons
PILLAR_ICON_PILL_LEFT = "◖"
PILLAR_ICON_PILL_RIGHT = "◗"
PILLAR_ICON_ACTIVE = "▶"
PILLAR_ICON_SUCCESS = "✔"
PILLAR_ICON_FAILURE = "✘"
PILLAR_ICON_IDLE = "○"


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

    def get_status_color(self) -> str:
        """Returns the base color hex or name for the current status."""
        if self.status == "active":
            return PILLAR_COLOR_ACTIVE
        elif self.status in self.SUCCESS_STATUSES:
            return PILLAR_COLOR_SUCCESS
        elif self.status in self.FAILURE_STATUSES:
            return PILLAR_COLOR_FAILURE
        else:
            return PILLAR_COLOR_DEFAULT

    def get_title_text(self) -> Text:
        """Returns the title text for the pillar (icon + name).

        Implements 'pill' shape for active/success/failed statuses (Issue #153).
        """
        status_color = self.get_status_color()
        name = self.name.upper()

        if self.status == "active":
            return Text.assemble(
                (PILLAR_ICON_PILL_LEFT, status_color),
                (f" {PILLAR_ICON_ACTIVE} {name} ", f"bold black on {status_color}"),
                (PILLAR_ICON_PILL_RIGHT, status_color),
                justify="center",
            )
        elif self.status in self.SUCCESS_STATUSES:
            return Text.assemble(
                (PILLAR_ICON_PILL_LEFT, status_color),
                (f" {PILLAR_ICON_SUCCESS} {name} ", f"bold black on {status_color}"),
                (PILLAR_ICON_PILL_RIGHT, status_color),
                justify="center",
            )
        elif self.status in self.FAILURE_STATUSES:
            return Text.assemble(
                (PILLAR_ICON_PILL_LEFT, status_color),
                (f" {PILLAR_ICON_FAILURE} {name} ", f"bold white on {status_color}"),
                (PILLAR_ICON_PILL_RIGHT, status_color),
                justify="center",
            )
        elif len(self.buffer) > 0:
            return Text(
                f"{PILLAR_ICON_SUCCESS} {name}",
                style=PILLAR_COLOR_IDLE_WITH_CONTENT,
                justify="center",
            )
        else:
            return Text(
                f"{PILLAR_ICON_IDLE} {name}",
                style=PILLAR_COLOR_IDLE_TEXT,
                justify="center",
            )

    def get_subtitle_text(self) -> Text:
        """Returns the subtitle text for the pillar (status + duration + completion time)."""
        duration_val = (
            self.duration
            if self.duration is not None
            else (
                int(time.time() - self.start_time)
                if self.start_time is not None and self.status == "active"
                else None
            )
        )

        time_parts = []
        if duration_val is not None:
            secs = int(duration_val)
            if secs >= 60:
                mins = secs // 60
                rem_secs = secs % 60
                time_parts.append(
                    f"[{mins}m {rem_secs}s]" if rem_secs > 0 else f"[{mins}m]"
                )
            else:
                time_parts.append(f"[{secs}s]")

        if self.completion_time is not None and self.status in self.COMPLETION_STATUSES:
            completion_dt = datetime.fromtimestamp(self.completion_time)
            time_parts.append(f"@{completion_dt.strftime('%H:%M:%S')}")

        status_desc = ""
        if self.status == "active":
            status_desc = "RUNNING"
        elif self.status in self.SUCCESS_STATUSES:
            status_desc = "SUCCESS"
        elif self.status in self.FAILURE_STATUSES:
            status_desc = "FAILED"

        res = Text(justify="center")
        if status_desc:
            res.append(status_desc, style=f"bold {self.get_status_color()}")
            if time_parts:
                res.append(" ")

        if time_parts:
            res.append(" ".join(time_parts), style="dim")

        return res

    def get_header_text(self) -> Text:
        """Returns the combined header text for the pillar (legacy support)."""
        title = self.get_title_text()
        subtitle = self.get_subtitle_text()
        if subtitle.plain:
            return Text.assemble(title, " ", subtitle)
        return title

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

        title_text = self.get_title_text()
        subtitle_text = self.get_subtitle_text()
        border_style = self.get_status_color()

        return Panel(
            self.get_content_renderable(),
            title=title_text,
            subtitle=subtitle_text,
            title_align="center",
            subtitle_align="center",
            border_style=border_style,
            expand=True,
            box=box.ROUNDED,
        )
