import contextlib
import heapq
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .column import SessionColumn


class SessionManager:
    """Manages the lifecycle and state of workflow sessions."""

    def __init__(
        self, log_dir: Path, sessions_per_page: int = 3, max_sessions: int = 100
    ):
        self.log_dir = log_dir
        self.sessions_per_page = sessions_per_page
        self.max_sessions = max_sessions
        self.sessions: dict[str, SessionColumn] = {}
        self.log_offsets: dict[str, int] = {}
        self.current_page = 0
        self.file_stats: dict[str, tuple[float, int]] = {}
        self.show_system_logs = False

    def _scan_log_files(self, log_dir: Path | str):
        """Recursively yields DirEntry objects for .jsonl files."""
        try:
            with os.scandir(log_dir) as it:
                for entry in it:
                    if entry.is_dir(follow_symlinks=False):
                        yield from self._scan_log_files(entry.path)
                    elif entry.is_file(follow_symlinks=False) and entry.name.endswith(
                        ".jsonl"
                    ):
                        yield entry
        except OSError:
            pass

    def update_from_logs(self) -> list[dict[str, Any]]:
        """
        Reads .jsonl files and updates session states.
        Returns a list of updates (session_id, events) to be processed by the UI.
        """
        if not self.log_dir.exists():
            return []

        # Find all .jsonl files recursively using os.scandir for performance
        entries = self._scan_log_files(self.log_dir)

        # Apply session limit: keep only the most recent files
        # heapq.nlargest is more efficient than full sort for large directories
        def get_mtime(entry):
            try:
                return entry.stat().st_mtime
            except OSError:
                return 0.0

        top_entries = heapq.nlargest(self.max_sessions, entries, key=get_mtime)

        # Convert back to Path objects and sort by mtime ascending to preserve processing order
        # (oldest to newest) which is what the original code did after slicing [-max_sessions:]
        log_files = [Path(e.path) for e in top_entries]
        with contextlib.suppress(OSError):
            log_files.sort(key=lambda f: f.stat().st_mtime)

        active_sids = set()
        log_entries_map = {}
        for fpath in log_files:
            # Derive session ID from relative path
            sid = str(fpath.relative_to(self.log_dir).with_suffix(""))
            active_sids.add(sid)
            log_entries_map[sid] = fpath

        # Remove stale sessions
        stale_sids = [sid for sid in self.sessions if sid not in active_sids]
        for sid in stale_sids:
            del self.sessions[sid]
            if sid in self.log_offsets:
                del self.log_offsets[sid]
            if sid in self.file_stats:
                del self.file_stats[sid]

        updates = []

        for sid, fpath in log_entries_map.items():
            try:
                stat = fpath.stat()
                mtime = stat.st_mtime
                size = stat.st_size
            except OSError:
                continue

            # Optimization: Skip file if mtime and size match cached values
            cached_stat = self.file_stats.get(sid)
            if cached_stat and cached_stat == (mtime, size):
                continue

            self.file_stats[sid] = (mtime, size)

            if sid not in self.sessions:
                self.sessions[sid] = SessionColumn(sid)
                self.sessions[sid].show_system_logs = self.show_system_logs

            # Optimization: If this is the first time we're reading this file,
            # and it's large (> 1MB), seek to 1MB from the end to avoid parsing everything.
            is_initial_read = sid not in self.log_offsets
            if is_initial_read:
                file_size = size
                if file_size > 1024 * 1024:
                    self.log_offsets[sid] = file_size - (1024 * 1024)
                else:
                    self.log_offsets[sid] = 0

            offset = self.log_offsets.get(sid, 0)
            events = []
            try:
                with open(fpath) as f:
                    if offset > 0:
                        f.seek(offset)
                        # If we seeked into the middle of a file (initial read of a large file),
                        # skip the first (likely partial) line.
                        if is_initial_read:
                            f.readline()

                    for line in f:
                        try:
                            event = json.loads(line)
                            events.append(event)
                            self._apply_event_to_session(self.sessions[sid], event)
                        except json.JSONDecodeError:
                            continue
                    self.log_offsets[sid] = f.tell()
            except Exception:
                pass

            if events:
                updates.append({"session_id": sid, "events": events})

        return updates

    def _apply_event_to_session(self, session: SessionColumn, event: dict[str, Any]):
        """Updates the internal session model with a single event."""
        node = event.get("node")
        etype = event.get("event_type")
        data = event.get("data")
        ts_str = event.get("timestamp")

        if ts_str:
            try:
                ts = datetime.fromisoformat(ts_str).timestamp()
                if session.created_at == 0 or ts < session.created_at:
                    session.created_at = ts
                    if session.activated_at == 0 or ts < session.activated_at:
                        session.activated_at = ts
            except (ValueError, TypeError):
                pass

        if node == "workflow" and etype == "workflow_status":
            session.workflow_status = data
            if data in ["success", "failed"] and ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str).timestamp()
                    session.completed_at = ts
                except (ValueError, TypeError):
                    pass
        elif node and node != "workflow":
            pillar = session.get_pillar(node)
            if etype in ["output", "info"]:
                # Default source based on etype if not present
                source = event.get("source")
                if not source:
                    source = "llm" if etype == "output" else "system"

                for line in data.splitlines():
                    if line.strip():
                        pillar.add_line(line, source=source)
            elif etype == "status":
                pillar.set_status(data, event.get("timestamp"))

    def get_sorted_sessions(self) -> list[SessionColumn]:
        """Returns sessions sorted by status (running first) and then by time."""

        def sort_key(s: SessionColumn):
            is_running = s.workflow_status == "running"
            if is_running:
                # Group 0: Running sessions, sorted by activation time (newest first for visibility)
                # Wait, original dashboard sorted oldest first?
                # "Group 0: Running sessions, sorted by activation time (oldest first)"
                # Let's keep it consistent: oldest running first.
                return (0, s.activated_at, s.session_id)
            else:
                # Group 1: Completed sessions, sorted by completion time (newest first)
                return (1, -s.completed_at, s.session_id)

        return sorted(self.sessions.values(), key=sort_key)

    @property
    def total_pages(self) -> int:
        """Returns the total number of pages based on current sessions."""
        num_sessions = len(self.sessions)
        if num_sessions == 0:
            return 1
        return (num_sessions + self.sessions_per_page - 1) // self.sessions_per_page

    def get_visible_sessions(self) -> tuple[list[SessionColumn], int, int]:
        """
        Returns the list of sessions for the current page, current page index, and total pages.
        """
        sorted_sessions = self.get_sorted_sessions()
        num_pages = self.total_pages

        # Clamp current_page based on actual number of pages
        self.current_page = max(0, min(self.current_page, num_pages - 1))

        start_idx = self.current_page * self.sessions_per_page
        end_idx = start_idx + self.sessions_per_page
        visible = sorted_sessions[start_idx:end_idx]

        return visible, self.current_page + 1, num_pages

    def next_page(self):
        """Moves to the next page, wrapping around."""
        num_pages = self.total_pages
        self.current_page = (self.current_page + 1) % num_pages

    def prev_page(self):
        """Moves to the previous page, wrapping around."""
        num_pages = self.total_pages
        self.current_page = (self.current_page - 1) % num_pages

    def toggle_system_logs(self):
        """Toggles visibility of system logs for all sessions."""
        self.show_system_logs = not self.show_system_logs
        for session in self.sessions.values():
            session.show_system_logs = self.show_system_logs
