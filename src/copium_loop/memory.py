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
