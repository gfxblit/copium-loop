import json
import os
import time
from datetime import datetime
from pathlib import Path


class Telemetry:
    """Handles logging of agent state and output to shared .jsonl files."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.log_dir = Path.home() / ".copium" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{session_id}.jsonl"

    def log(self, node: str, event_type: str, data: str | dict):
        """Logs an event to the session's .jsonl file."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "node": node,
            "event_type": event_type,  # 'status', 'output', 'metric'
            "data": data,
        }
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def log_output(self, node: str, chunk: str):
        """Logs a chunk of output from an agent."""
        if not chunk:
            return
        self.log(node, "output", chunk)

    def log_status(self, node: str, status: str):
        """Logs a status change for a node (e.g., 'active', 'idle', 'error', 'success')."""
        self.log(node, "status", status)

    def log_metric(self, node: str, metric_name: str, value: float):
        """Logs a metric for a node (e.g., 'latency', 'tokens')."""
        self.log(node, "metric", {"name": metric_name, "value": value})


_telemetry_instance = None


def get_telemetry() -> Telemetry:
    """Returns the global telemetry instance."""
    global _telemetry_instance
    if _telemetry_instance is None:
        # We need a session ID. We can use the tmux session or a random one.
        # For now, let's try to get it from environment or generate a timestamp-based one.
        session_id = os.environ.get("TMUX_PANE", f"session_{int(time.time())}")
        # Try to get actual tmux session name if possible
        try:
            import subprocess
            res = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=False
            )
            if res.returncode == 0:
                name = res.stdout.strip()
                pane = os.environ.get("TMUX_PANE", "0")
                session_id = f"{name}_{pane}"
        except Exception:
            pass
        _telemetry_instance = Telemetry(session_id)
    return _telemetry_instance
