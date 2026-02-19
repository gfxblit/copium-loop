import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SessionData:
    """Data structure for a persistent session."""

    session_id: str
    engine_state: dict[str, dict[str, Any]] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "engine_state": self.engine_state,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        return cls(
            session_id=data["session_id"],
            engine_state=data.get("engine_state", {}),
            metadata=data.get("metadata", {}),
        )


class SessionManager:
    """Manages persistent session state."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state_dir = Path.home() / ".copium" / "sessions"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f"{session_id}.json"
        self._data: SessionData | None = None
        self._load()

    def _load(self):
        """Loads session data from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self._data = SessionData.from_dict(data)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Warning: Failed to load session state: {e}")
                # Fallback to empty session if corrupted
                self._data = SessionData(session_id=self.session_id)
        else:
            self._data = SessionData(session_id=self.session_id)

    def _save(self):
        """Atomically saves session data to disk."""
        if not self._data:
            return

        # Write to temp file first
        with tempfile.NamedTemporaryFile(
            mode="w", dir=self.state_dir, delete=False
        ) as tmp:
            json.dump(self._data.to_dict(), tmp, indent=2)
            tmp_path = Path(tmp.name)

        # Atomic move
        try:
            os.replace(tmp_path, self.state_file)
        except OSError as e:
            print(f"Warning: Failed to save session state: {e}")
            if tmp_path.exists():
                os.remove(tmp_path)

    def update_engine_state(self, engine_type: str, key: str, value: Any):
        """Updates the engine state for a specific engine and key."""
        if not self._data:
            self._load()
        if engine_type not in self._data.engine_state:
            self._data.engine_state[engine_type] = {}
        self._data.engine_state[engine_type][key] = value
        self._save()

    def get_engine_state(self, engine_type: str, key: str) -> Any | None:
        """Retrieves the engine state for a specific engine and key."""
        if not self._data:
            self._load()

        if (
            engine_type in self._data.engine_state
            and key in self._data.engine_state[engine_type]
        ):
            return self._data.engine_state[engine_type][key]

        return None

    def update_jules_session(self, node: str, jules_session_id: str, prompt_hash: str = "default_hash"):
        """Updates the Jules session ID for a specific node."""
        self.update_engine_state("jules", node, {"session_id": jules_session_id, "prompt_hash": prompt_hash})

    def get_jules_session(self, node: str) -> str | None:
        """Retrieves the Jules session ID for a specific node."""
        state = self.get_engine_state("jules", node)
        if isinstance(state, dict):
            return state.get("session_id")
        return None

    def get_all_jules_sessions(self) -> dict[str, str]:
        """Retrieves all Jules session IDs."""
        if not self._data:
            self._load()

        sessions = {}
        if "jules" in self._data.engine_state:
            for k, v in self._data.engine_state["jules"].items():
                if isinstance(v, dict):
                    session_id = v.get("session_id")
                    if session_id:
                        sessions[k] = session_id
        return sessions

    def update_metadata(self, key: str, value: str):
        """Updates arbitrary metadata."""
        if not self._data:
            self._load()
        self._data.metadata[key] = value
        self._save()

    def get_metadata(self, key: str) -> str | None:
        """Retrieves metadata."""
        if not self._data:
            self._load()
        return self._data.metadata.get(key)
