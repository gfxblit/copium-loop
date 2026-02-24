import atexit
import concurrent.futures
import json
from datetime import datetime
from pathlib import Path


class Telemetry:
    """Handles logging of agent state and output to shared .jsonl files."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.log_dir = Path.home() / ".copium" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / f"{session_id}.jsonl"
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        atexit.register(self._executor.shutdown)

    def flush(self):
        """Waits for all pending log writes to complete."""
        self._executor.submit(lambda: None).result()

    def log(self, node: str, event_type: str, data: str | dict, source: str = "system"):
        """Logs an event to the session's .jsonl file."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "node": node,
            "event_type": event_type,  # 'status', 'output', 'metric'
            "source": source,  # 'system' or 'llm'
            "data": data,
        }
        self._executor.submit(self._write_event, event)

    def _write_event(self, event: dict):
        """Writes an event to disk. Called by the thread executor."""
        # Ensure parent directory exists for session ID with slashes
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def log_output(self, node: str, chunk: str):
        """Logs a chunk of output from an agent."""
        if not chunk:
            return
        self.log(node, "output", chunk, source="llm")

    def log_info(self, node: str, info: str):
        """Logs system-level info from an agent."""
        if not info:
            return
        self.log(node, "info", info, source="system")

    def log_status(self, node: str, status: str):
        """Logs a status change for a node (e.g., 'active', 'idle', 'error', 'success')."""
        self.log(node, "status", status, source="system")

    def log_metric(self, node: str, metric_name: str, value: float):
        """Logs a metric for a node (e.g., 'latency', 'tokens')."""
        self.log(node, "metric", {"name": metric_name, "value": value}, source="system")

    def log_workflow_status(self, status: str):
        """Logs a workflow-level status change (e.g., 'running', 'success', 'failed')."""
        self.log("workflow", "workflow_status", status, source="system")

    def read_log(self) -> list[dict]:
        """Reads all events from the session's log file."""
        self.flush()
        if not self.log_file.exists():
            return []

        events = []
        with open(self.log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events

    def get_formatted_log(
        self, max_lines: int = 100, max_output_chars: int = 200
    ) -> str:
        """
        Returns a human-readable summary of the telemetry log.

        Optimizations for context window:
        - Filters out 'metric' events.
        - Truncates 'output' content to `max_output_chars`.
        - Enforces `max_lines` via Head/Tail windowing (keeps first 20 + last N).
        """
        events = self.read_log()
        if not events:
            return "No telemetry log found."

        # Isolate events from the last run
        events, _ = self._isolate_events(events)
        if not events:
            return "No events found in current run."

        # Filter out noisy events
        relevant_events = [e for e in events if e.get("event_type") != "metric"]

        # Apply Head/Tail windowing if too large
        if len(relevant_events) > max_lines:
            head_size = 20
            tail_size = max_lines - head_size
            removed_events = relevant_events[head_size:-tail_size]
            removed_count = len(removed_events)
            removed_nodes = sorted({e.get("node", "unknown") for e in removed_events})
            nodes_str = ", ".join(removed_nodes)
            relevant_events = (
                relevant_events[:head_size]
                + [
                    {
                        "node": "system",
                        "event_type": "info",
                        "data": f"removed middle text of {removed_count} lines from {nodes_str} for brevity",
                    }
                ]
                + relevant_events[-tail_size:]
            )

        lines = []
        for event in relevant_events:
            node = event.get("node", "unknown")
            event_type = event.get("event_type", "unknown")
            data = event.get("data", "")
            timestamp = event.get("timestamp", "")

            # Truncate output, prompts and info
            if event_type in ["output", "prompt", "info"] and isinstance(data, str):
                if len(data) > max_output_chars:
                    data = data[:max_output_chars] + "... (truncated)"
                # Clean up newlines for compact log
                data = data.replace("\n", "\\n")

            # Format timestamp
            ts_prefix = ""
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp)
                    ts_prefix = f"[{dt.strftime('%H:%M:%S')}] "
                except (ValueError, TypeError):
                    pass

            lines.append(f"{ts_prefix}{node}: {event_type}: {data}")

        return "\n".join(lines)

    def _isolate_events(self, events: list[dict]) -> tuple[list[dict], str | None]:
        """
        Isolates events from the last run (starting with 'INIT:').

        Returns:
            tuple: (isolated_events, prompt)
        """
        last_system_init_idx = -1
        last_any_init_idx = -1
        for i in range(len(events) - 1, -1, -1):
            event = events[i]
            data = str(event.get("data", ""))
            if "INIT: Starting workflow with prompt:" in data:
                # Prioritize system/info events
                if event.get("source") == "system" or event.get("event_type") == "info":
                    last_system_init_idx = i
                    break
                if last_any_init_idx == -1:
                    last_any_init_idx = i

        last_init_idx = (
            last_system_init_idx if last_system_init_idx != -1 else last_any_init_idx
        )

        prompt = None
        if last_init_idx != -1:
            # Extract prompt from the last INIT: event
            data = str(events[last_init_idx].get("data", ""))
            prompt = data.split("Starting workflow with prompt:", 1)[1].strip()
            # Slice events to only consider this run
            events = events[last_init_idx:]

        return events, prompt

    def get_last_incomplete_node(self) -> tuple[str | None, dict]:
        """
        Determines which node to resume from based on log events.

        Returns:
            tuple: (node_name, metadata) where node_name is the node to resume from,
                   or (None, metadata) if workflow is complete or cannot be resumed.
                   metadata contains info like 'reason', 'workflow_status', etc.
        """
        events = self.read_log()
        if not events:
            return None, {"reason": "no_log_found"}

        # Isolate events from the last run
        events, _ = self._isolate_events(events)

        # Check if workflow completed successfully
        workflow_events = [
            e
            for e in events
            if e.get("node") == "workflow" and e.get("event_type") == "workflow_status"
        ]
        if workflow_events:
            last_workflow_status = workflow_events[-1].get("data")
            if last_workflow_status == "success":
                return None, {
                    "reason": "workflow_completed",
                    "status": last_workflow_status,
                }

        # Track the last status for each node
        node_statuses = {}
        for event in events:
            if event.get("event_type") == "status":
                node = event.get("node")
                status = event.get("data")
                if node and node != "workflow":
                    if node not in node_statuses:
                        node_statuses[node] = []
                    node_statuses[node].append(status)

        # Determine which node was last active but didn't complete
        # Node progression: coder -> tester -> architect -> reviewer -> pr_pre_checker -> journaler -> pr_creator
        node_order = [
            "coder",
            "tester",
            "architect",
            "reviewer",
            "pr_pre_checker",
            "journaler",
            "pr_creator",
        ]

        # Find the last node that was active
        last_active_node = None
        for node in reversed(node_order):
            if node in node_statuses and node_statuses[node]:
                last_status = node_statuses[node][-1]
                # If the node is active or failed/error, we should resume from it
                if last_status in ["active", "failed", "rejected", "error"]:
                    last_active_node = node
                    break
                # If it succeeded, check the next node in the workflow
                elif last_status in ["success", "approved", "idle"]:
                    # Find the next node in the progression
                    current_idx = node_order.index(node)
                    if current_idx < len(node_order) - 1:
                        last_active_node = node_order[current_idx + 1]
                    break

        if last_active_node:
            return last_active_node, {
                "reason": "incomplete",
                "last_statuses": node_statuses,
            }

        # Default to coder if we can't determine
        return "coder", {"reason": "uncertain", "last_statuses": node_statuses}

    def reconstruct_state(self, reset_retries: bool = True) -> dict:
        """
        Reconstructs workflow state from log events.

        Args:
            reset_retries (bool): Whether to reset retry_count to 0. Defaults to True.

        Returns:
            dict: Partial state that can be merged with initial state
        """
        events = self.read_log()
        state = {}

        # Isolate events from the last run
        events, prompt = self._isolate_events(events)
        if prompt:
            state["prompt"] = prompt

        # Reconstruct engine from output logs (in current run)
        for event in events:
            if event.get("event_type") == "output":
                data = str(event.get("data", ""))
                if "Jules session created" in data:
                    state["engine_name"] = "jules"
                    break
        else:
            state["engine_name"] = "gemini"

        # We start with 0 retries on continue to give the resumed session a fresh budget
        if reset_retries:
            state["retry_count"] = 0

        node_statuses = {}
        for event in events:
            if event.get("event_type") == "status":
                node = event.get("node")
                status = event.get("data")
                if node and node != "workflow":
                    if node not in node_statuses:
                        node_statuses[node] = []
                    node_statuses[node].append(status)

        # Determine test_output status
        if "tester" in node_statuses:
            last_tester_status = node_statuses["tester"][-1]
            if last_tester_status == "success":
                state["test_output"] = "PASS"
            elif last_tester_status in ["failed", "error"]:
                state["test_output"] = "FAIL"

        # Determine review_status
        if "reviewer" in node_statuses:
            last_reviewer_status = node_statuses["reviewer"][-1]
            if last_reviewer_status == "approved":
                state["review_status"] = "approved"
            elif last_reviewer_status == "rejected":
                state["review_status"] = "rejected"

        # Check PR creator status
        if "pr_creator" in node_statuses:
            last_pr_status = node_statuses["pr_creator"][-1]
            if last_pr_status == "success":
                state["review_status"] = "pr_created"
            elif last_pr_status == "failed":
                state["review_status"] = "pr_failed"

        return state


_telemetry_instance = None


def find_latest_session() -> str | None:
    """
    Finds the most recent session ID from the log directory.

    Returns:
        str: The session ID of the most recent log file, or None if no logs exist
    """
    log_dir = Path.home() / ".copium" / "logs"
    if not log_dir.exists():
        return None

    # Find all .jsonl files recursively
    log_files = list(log_dir.glob("**/*.jsonl"))
    if not log_files:
        return None

    # Sort by modification time, most recent first
    log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    # Return the session ID (path relative to log_dir without extension)
    latest_file = log_files[0]
    return str(latest_file.relative_to(log_dir).with_suffix(""))


def get_telemetry() -> Telemetry:
    """Returns the global telemetry instance with a session ID derived from the git repo and branch."""
    global _telemetry_instance
    if _telemetry_instance is None:
        import re
        import subprocess

        # Strictly derive session ID from repo and branch
        try:
            # 1. Get repo name (from remote origin if possible, else from local directory)
            repo_name = None
            res = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                check=False,
            )

            if res.returncode == 0:
                url = res.stdout.strip()
                # Extract owner and repo from various git URL formats
                match = re.search(r"(?<!/)[:/]([\w\-\.]+/[\w\-\.]+?)(?:\.git)?/?$", url)
                if match:
                    repo_name = match.group(1).replace("/", "-")

            if not repo_name:
                # Fallback to local directory name if no remote or remote doesn't match
                res = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if res.returncode == 0:
                    repo_name = Path(res.stdout.strip()).name
                else:
                    raise RuntimeError(
                        "Not a git repository: Could not determine repository root."
                    )

            # 2. Get branch name
            res = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                branch_name = res.stdout.strip()
                if not branch_name:
                    # Detached HEAD? Fallback to commit hash
                    res = subprocess.run(
                        ["git", "rev-parse", "--short", "HEAD"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    branch_name = (
                        res.stdout.strip() if res.returncode == 0 else "unknown"
                    )
            else:
                raise RuntimeError(
                    "Not a git repository: Could not determine branch name."
                )

            session_id = f"{repo_name}/{branch_name}"
            _telemetry_instance = Telemetry(session_id)

        except RuntimeError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"Failed to derive session ID: {e}") from e

    return _telemetry_instance
