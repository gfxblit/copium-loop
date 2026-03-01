
with open("src/copium_loop/ui/manager.py") as f:
    code = f.read()

# Add imports
if "import heapq\n" not in code:
    code = code.replace("import json\n", "import heapq\nimport json\nimport os\n")

# Add _scan_log_files method
scan_method = """
    def _scan_log_files(self, path: Path | str):
        try:
            for entry in os.scandir(path):
                if entry.is_dir(follow_symlinks=False):
                    yield from self._scan_log_files(entry.path)
                elif entry.is_file() and entry.name.endswith('.jsonl'):
                    yield entry
        except OSError:
            pass

    def update_from_logs(self) -> list[dict[str, Any]]:"""

code = code.replace(
    "    def update_from_logs(self) -> list[dict[str, Any]]:", scan_method
)

# Replace rglob logic
old_logic = """        # Find all .jsonl files recursively
        log_files = list(self.log_dir.rglob("*.jsonl"))

        # Sort by mtime to preserve consistent processing order
        with contextlib.suppress(OSError):
            log_files.sort(key=lambda f: f.stat().st_mtime)

        # Apply session limit: keep only the most recent files
        if len(log_files) > self.max_sessions:
            log_files = log_files[-self.max_sessions :]"""

new_logic = """        # Find all .jsonl files recursively using os.scandir for performance
        # We need to find the most recent `self.max_sessions` files based on mtime.
        # heapq.nlargest is O(N log K) where N is total files and K is max_sessions.
        def get_file_info(entry):
            try:
                stat = entry.stat()
                return (stat.st_mtime, Path(entry.path), stat.st_size)
            except OSError:
                return (0, Path(entry.path), 0)

        # Use a generator to avoid loading all FileInfos into memory
        file_infos = (get_file_info(e) for e in self._scan_log_files(self.log_dir))

        # Get the most recent max_sessions files.
        # Since we want to process them in consistent order (oldest first among the recent ones),
        # we first get the n largest by mtime, then reverse/sort them.
        recent_files = heapq.nlargest(self.max_sessions, file_infos, key=lambda x: x[0])
        recent_files.sort(key=lambda x: x[0])

        # We will map sid to (mtime, size) to avoid re-statting later
        pre_statted_info = {}
        log_files = []
        for mtime, path, size in recent_files:
            log_files.append(path)
            # Derive session ID from relative path
            sid = str(path.relative_to(self.log_dir).with_suffix(""))
            pre_statted_info[sid] = (mtime, size)"""

code = code.replace(old_logic, new_logic)

with open("src/copium_loop/ui/manager.py", "w") as f:
    f.write(code)
