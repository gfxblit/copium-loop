import os
import subprocess


def extract_tmux_session(session_id: str) -> str | None:
    """Extracts the tmux session name or pane ID from a session_id.

    Session IDs are typically formatted as {tmux_session}_{pane_id} (e.g., work_%1)
    or session_{timestamp} (e.g., session_123456789).
    Returns the most specific target possible.
    """
    if not session_id:
        return None

    # If it's already a pane ID, return it
    if session_id.startswith("%") and session_id[1:].isdigit():
        return session_id

    if "_" in session_id:
        parts = session_id.rsplit("_", 1)
        suffix = parts[1]

        # Case 1: suffix is a pane ID (starts with %)
        # Pane IDs are unique and the best target for switching.
        if suffix.startswith("%") and suffix[1:].isdigit():
            return suffix

        # Note: We used to treat session_timestamp as None, but existing tests
        # require returning the full ID. We preserve it to allow potential
        # matches if the user named their session thus.
        return session_id

    # Otherwise, it's likely just the session name
    return session_id


def switch_to_tmux_session(session_name: str):
    """Switches the current tmux client to the specified session, window, or pane.

    Utilizes extract_tmux_session to determine the best target.
    """
    if not session_name or not os.environ.get("TMUX"):
        return

    target = extract_tmux_session(session_name)
    if not target:
        return

    try:
        # We use 'tmux switch-client' which is the standard way to switch sessions/panes.
        # It works for sessions, windows, and panes (via %ID).
        subprocess.run(
            ["tmux", "switch-client", "-t", target],
            check=True,
            capture_output=True,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # If the primary target fails, we stop. The architect deemed the previous
        # fallback logic (stripping suffixes blindly) as inferior/incorrect.
        pass
    except Exception as e:
        import sys

        print(
            f"Unexpected error switching to tmux session '{session_name}': {e}",
            file=sys.stderr,
        )
