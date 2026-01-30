import os
import subprocess


def extract_tmux_session(session_id: str) -> str | None:
    """Extracts the tmux session name from a session_id.

    Session IDs are formatted as {tmux_session}, {tmux_session}_{pane}
    or session_{timestamp}.
    Returns the tmux session name if it exists, None otherwise.
    """
    # Handle old format: {tmux_session}_{pane}
    # We check if it ends with _%digit or _digit
    if "_" in session_id:
        parts = session_id.rsplit("_", 1)
        suffix = parts[1]

        # If suffix is a pane ID (starts with %)
        if suffix.startswith("%") and suffix[1:].isdigit():
             return parts[0]

        # If suffix is digits, we need to distinguish between a pane index and a timestamp
        # Timestamps (like in session_1234567890) are usually long (10+ digits).
        # Pane indices are usually short.
        # We'll use a threshold of 8 digits.
        if suffix.isdigit():
             if len(suffix) < 8:
                 return parts[0]
             # If longer, assume it's part of the name (e.g. session_TIMESTAMP)
             return session_id

    # Otherwise, the session_id is the tmux session name
    return session_id


def switch_to_tmux_session(session_name: str):
    """Switches the current tmux client to the specified session."""
    # Check if we're running inside tmux
    if not os.environ.get("TMUX"):
        return  # Not in tmux, silently ignore

    try:
        subprocess.run(
            ["tmux", "switch-client", "-t", "--", session_name],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        # Session doesn't exist or other error, silently ignore
        pass
    except Exception as e:
        import sys

        print(
            f"Unexpected error switching to tmux session '{session_name}': {e}",
            file=sys.stderr,
        )
