import os
import subprocess


def extract_tmux_session(session_id: str) -> str | None:
    """Extracts the tmux session name or pane ID from a session_id.

    Session IDs are formatted as {tmux_session}, {tmux_session}_{pane}
    or session_{timestamp}.
    Returns the pane ID if it exists (most precise), otherwise the session name.
    """
    # Handle old format: {tmux_session}_{pane}
    # We check if it ends with _%digit or _digit
    if "_" in session_id:
        parts = session_id.rsplit("_", 1)
        suffix = parts[1]

        # If suffix is a pane ID (starts with %)
        # Pane IDs are unique across the entire tmux server, so they are the best target.
        if suffix.startswith("%") and suffix[1:].isdigit():
             return suffix

        # We used to strip short numeric suffixes (len < 8) to handle legacy session_pane IDs.
        # However, this caused collisions with valid session names like 'project_1'.
        # Since we now default to using the full session name as the ID, we preserve it.
        return session_id

    # Otherwise, the session_id is the tmux session name
    return session_id


def switch_to_tmux_session(session_name: str):
    """Switches the current tmux client to the specified session or pane."""
    # Check if we're running inside tmux
    if not os.environ.get("TMUX"):
        return  # Not in tmux, silently ignore

    try:
        subprocess.run(
            ["tmux", "switch-client", "-t", session_name],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        # Session doesn't exist or other error, silently ignore
        pass
    except FileNotFoundError:
        # tmux command not found, silently ignore
        pass
    except Exception as e:
        import sys

        print(
            f"Unexpected error switching to tmux session '{session_name}': {e}",
            file=sys.stderr,
        )
