import datetime
import os
import re
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

    def get_project_memories(self) -> list[str]:
        """Returns a list of facts from the local GEMINI.md file."""
        if not self.project_memory_file.exists():
            return []

        content = self.project_memory_file.read_text()
        # Regex to match "- [timestamp] Fact" and capture "Fact"
        pattern = r"- \[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] (.*)"
        return re.findall(pattern, content)
