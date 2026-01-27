import os
import re
import select
import sys


class InputReader:
    """Handles non-blocking buffered keyboard input reading with ANSI escape sequence support."""

    # Pattern to match ANSI escape sequences (e.g., arrows, shift+tab)
    SEQ_PATTERN = re.compile(r"^(\x1b\[[0-9;]*[A-Za-z]|\x1b[\ \[O][A-Z])", re.DOTALL)

    def __init__(self):
        self._buffer = ""

    def get_key(self, timeout: float = 0.05) -> str | None:
        """Reads a single key or escape sequence from stdin, using an internal buffer."""
        # Try to read more data if buffer is empty or could be an incomplete sequence
        if (
            not self._buffer
            or (
                self._buffer.startswith("\x1b")
                and not self.SEQ_PATTERN.match(self._buffer)
            )
        ) and select.select([sys.stdin], [], [], timeout)[0]:
            try:
                chunk = os.read(sys.stdin.fileno(), 1024).decode(errors="ignore")
                if chunk:
                    self._buffer += chunk
            except Exception:
                pass

        if not self._buffer:
            return None

        # Check for escape sequences
        if self._buffer.startswith("\x1b"):
            match = self.SEQ_PATTERN.match(self._buffer)
            if match:
                key = match.group(0)
                self._buffer = self._buffer[len(key) :]
                return key

            # If it's an incomplete sequence, wait for more
            if self._buffer.startswith(("\x1b[", "\x1bO")):
                return None

            # If it's just \x1b, return it as the Escape key
            if self._buffer == "\x1b":
                self._buffer = ""
                return "\x1b"

        # Default: return a single character
        key = self._buffer[0]
        self._buffer = self._buffer[1:]
        return key
