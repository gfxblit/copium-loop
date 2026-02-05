import json
import shutil
import subprocess
import time


class CodexbarClient:
    """Client for interacting with the codexbar CLI to fetch usage quotas."""

    def __init__(self):
        self._cache_ttl = 60
        self._last_check = 0
        self._cached_data: dict | None = None
        self._executable = None

    def _find_executable(self) -> str | None:
        if self._executable:
            return self._executable

        # Check standard paths if not in PATH (though shutil.which checks PATH)
        exe = shutil.which("codexbar")
        if exe:
            self._executable = exe
            return exe

        # Fallback explicit checks if not in PATH for some reason
        for path in ["/usr/local/bin/codexbar", "/opt/homebrew/bin/codexbar"]:
            if shutil.which(path):
                self._executable = path
                return path

        return None

    def get_usage(self) -> dict | None:
        """
        Fetches usage statistics from codexbar.
        Returns a dictionary with 'pro', 'flash', and 'reset' keys, or None if failed.
        """
        now = time.time()
        if self._cached_data and (now - self._last_check < self._cache_ttl):
            return self._cached_data

        executable = self._find_executable()
        if not executable:
            return None

        try:
            result = subprocess.run(
                [executable, "--format", "json"],
                capture_output=True,
                text=True,
                timeout=5.0,
                check=False,
            )

            if result.returncode != 0:
                return None

            raw_data = json.loads(result.stdout)

            # Normalize data: codexbar returns a list of provider objects.
            # We look for the gemini provider and extract primary/secondary usage.
            normalized = {"pro": 0, "flash": 0, "reset": "?"}
            
            if isinstance(raw_data, list) and len(raw_data) > 0:
                # Default to first provider if we can't find 'gemini'
                provider_data = raw_data[0]
                for p in raw_data:
                    if p.get("provider") == "gemini":
                        provider_data = p
                        break
                
                usage = provider_data.get("usage", {})
                primary = usage.get("primary", {})
                secondary = usage.get("secondary", {})
                
                normalized["pro"] = primary.get("usedPercent", 0)
                normalized["flash"] = secondary.get("usedPercent", 0)
                normalized["reset"] = primary.get("resetDescription", "?")
            elif isinstance(raw_data, dict):
                # Fallback for old/alternative format if it was already flat
                normalized["pro"] = raw_data.get("pro", 0)
                normalized["flash"] = raw_data.get("flash", 0)
                normalized["reset"] = raw_data.get("reset", "?")

            self._cached_data = normalized
            self._last_check = now
            return normalized

        except (subprocess.SubprocessError, json.JSONDecodeError, OSError, KeyError, TypeError):
            return None
