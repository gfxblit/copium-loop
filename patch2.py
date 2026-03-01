
with open("src/copium_loop/ui/manager.py") as f:
    code = f.read()

# Replace redundant sid deriving logic and statting
old_logic = """        active_sids = set()
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
                continue"""

new_logic = """        active_sids = set()
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
            # Optimization: Use pre-statted info from os.scandir to avoid additional stat calls
            if sid in pre_statted_info:
                mtime, size = pre_statted_info[sid]
            else:
                try:
                    stat = fpath.stat()
                    mtime = stat.st_mtime
                    size = stat.st_size
                except OSError:
                    continue"""

code = code.replace(old_logic, new_logic)

with open("src/copium_loop/ui/manager.py", "w") as f:
    f.write(code)
