import datetime
import os
from pathlib import Path


class MemoryManager:
    def __init__(self, project_root=None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.project_memory_file = self.project_root / "GEMINI.md"
        self.global_memory_file = Path(os.path.expanduser("~/.gemini/GEMINI.md"))

    def log_learning(self, fact: str):
        """Appends a timestamped, concise lesson to ./GEMINI.md."""
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"- [{timestamp}] {fact}\n"

        if not self.project_memory_file.exists():
            self.project_memory_file.write_text("# Project Memory\n\n")

        with open(self.project_memory_file, "a") as f:
            f.write(entry)

    def get_project_context(self) -> str:
        """Reads and formats local rules/history from ./GEMINI.md."""
        if not self.project_memory_file.exists():
            return ""
        return self.project_memory_file.read_text()

    def get_global_context(self) -> str:
        """Reads and formats global rules/history from ~/.gemini/GEMINI.md."""
        if not self.global_memory_file.exists():
            return ""
        return self.global_memory_file.read_text()

    def get_all_memories(self) -> str:
        """Combines global and project memories."""
        global_ctx = self.get_global_context()
        project_ctx = self.get_project_context()

        combined = ""
        if global_ctx:
            combined += "## Global Persona Memory\n"
            combined += global_ctx
            combined += "\n\n"

        if project_ctx:
            combined += "## Project-Specific Memory\n"
            combined += project_ctx
            combined += "\n"

        return combined.strip()
