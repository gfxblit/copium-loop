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
    agent_state: dict[str, Any] = field(default_factory=dict)
    branch_name: str | None = None
    repo_root: str | None = None
    engine_name: str | None = None
    original_prompt: str | None = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "engine_state": self.engine_state,
            "metadata": self.metadata,
            "agent_state": self.agent_state,
            "branch_name": self.branch_name,
            "repo_root": self.repo_root,
            "engine_name": self.engine_name,
            "original_prompt": self.original_prompt,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SessionData":
        return cls(
            session_id=data["session_id"],
            engine_state=data.get("engine_state", {}),
            metadata=data.get("metadata", {}),
            agent_state=data.get("agent_state", {}),
            branch_name=data.get("branch_name"),
            repo_root=data.get("repo_root"),
            engine_name=data.get("engine_name"),
            original_prompt=data.get("original_prompt"),
        )


class SessionManager:
    """Manages persistent session state."""

    def __init__(self, session_id: str):
        # Prevent path traversal
        if not session_id or session_id in (".", ".."):
            raise ValueError("Invalid session ID")

        # Replace characters that are problematic in filenames
        # We allow '/' because the session ID might be "owner/repo" which we want
        # to map to "owner_repo" or similar, but here we just replace path separators
        # to flatten the directory structure and prevent traversal.
        # Actually, simply taking the basename is risky if the ID is meant to be unique globally.
        # A better approach is to sanitize the ID to only allow safe characters.
        # However, to minimally impact existing behavior while fixing traversal,
        # we will ensure the resolved path stays within the state_dir.

        self.state_dir = Path.home() / ".copium" / "sessions"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize session_id to prevent path traversal
        # We replace any path separators with underscores to flatten the structure
        safe_session_id = session_id.replace(os.sep, "_")
        if os.altsep:
            safe_session_id = safe_session_id.replace(os.altsep, "_")

        # Remove any ".." components if they somehow survived (though replacing sep should handle it)
        if ".." in safe_session_id:
            raise ValueError("Invalid session ID: contains '..'")

        self.session_id = session_id  # Keep original ID for logic
        self.state_file = self.state_dir / f"{safe_session_id}.json"

        # Final check to be absolutely sure
        try:
            # We use strict=False to allow resolving paths that don't exist yet (for new sessions)
            # This is available in Python 3.10+ (and default behavior in older versions was strict=False)
            self.state_file.resolve(strict=False).relative_to(
                self.state_dir.resolve(strict=False)
            )
        except ValueError:
            # This should be unreachable with the replacement above, but defense in depth
            raise ValueError(
                f"Invalid session ID: {session_id} results in path traversal"
            ) from None

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

        # Ensure parent directory exists for session ID with slashes
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

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

    def update_jules_session(self, node: str, jules_session_id: str, prompt_hash: str):
        """Updates the Jules session ID for a specific node."""
        self.update_engine_state(
            "jules", node, {"session_id": jules_session_id, "prompt_hash": prompt_hash}
        )

    def get_jules_session(self, node: str) -> str | None:
        """Retrieves the Jules session ID for a specific node."""
        state = self.get_engine_state("jules", node)
        if isinstance(state, dict) and state.get("prompt_hash"):
            return state.get("session_id")
        return None

    def get_all_jules_sessions(self) -> dict[str, str]:
        """Retrieves all Jules session IDs."""
        if not self._data:
            self._load()

        sessions = {}
        if "jules" in self._data.engine_state:
            for k, v in self._data.engine_state["jules"].items():
                # No backward compatibility: only return dict with prompt_hash and session_id
                if isinstance(v, dict) and v.get("prompt_hash") and v.get("session_id"):
                    sessions[k] = v["session_id"]
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

    def update_agent_state(self, state: dict[str, Any]):
        """Updates the full AgentState."""
        if not self._data:
            self._load()
        self._data.agent_state = state
        self._save()

    def get_agent_state(self) -> dict[str, Any]:
        """Retrieves the full AgentState."""
        if not self._data:
            self._load()
        return self._data.agent_state

    def get_resumed_state(self) -> dict[str, Any]:
        """
        Retrieves the AgentState for a resumed session, resetting retry budget.

        This encapsulates the 'resume' state transition.
        """
        state = self.get_agent_state()
        if state:
            state["retry_count"] = 0
            self.update_agent_state(state)
        return state

    def get_branch_name(self) -> str | None:
        """Retrieves the branch name."""
        if not self._data:
            self._load()
        return self._data.branch_name

    def get_repo_root(self) -> str | None:
        """Retrieves the repo root."""
        if not self._data:
            self._load()
        return self._data.repo_root

    def get_engine_name(self) -> str | None:
        """Retrieves the engine name."""
        if not self._data:
            self._load()
        return self._data.engine_name

    def get_original_prompt(self) -> str | None:
        """Retrieves the original prompt."""
        if not self._data:
            self._load()
        return self._data.original_prompt

    def update_session_info(
        self,
        branch_name: str | None = None,
        repo_root: str | None = None,
        engine_name: str | None = None,
        original_prompt: str | None = None,
    ):
        """Updates sticky session information."""
        if not self._data:
            self._load()
        if branch_name is not None:
            self._data.branch_name = branch_name
        if repo_root is not None:
            self._data.repo_root = repo_root
        if engine_name is not None:
            self._data.engine_name = engine_name
        if original_prompt is not None:
            self._data.original_prompt = original_prompt
        self._save()
