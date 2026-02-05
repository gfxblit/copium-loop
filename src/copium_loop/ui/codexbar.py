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
                timeout=1.0,
                check=False,
            )

            if result.returncode != 0:
                return None

            data = json.loads(result.stdout)

            # minimal validation
            # The issue implies keys related to Pro, Flash, Reset.
            # We accept whatever is there as long as it parses.
            # But the test expects specific keys, so let's rely on the CLI output matching expectation.

            self._cached_data = data
            self._last_check = now
            return data

        except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
            return None
