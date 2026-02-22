import os
import subprocess


def extract_tmux_session(session_id: str) -> str | None:
    """Extracts the tmux session name or pane ID from a session_id.

    Session IDs are typically formatted as {repo}/{tmux_session}_{pane_id} (e.g., myrepo/work_%1)
    or session_{timestamp} (e.g., session_123456789).
    Returns the most specific target possible.
    """
    if not session_id:
        return None

    # Strip any directory prefix (e.g., repo/session -> session)
    if "/" in session_id:
        session_id = session_id.rsplit("/", 1)[1]

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

        # Preserve the ID after stripping slash for potential matches
        return session_id

    # Otherwise, it's likely just the session name
    return session_id


def switch_to_tmux_session(session_name: str):
    """Switches the current tmux client to the specified session, window, or pane.

    Tries multiple variations of the target name if the initial attempt fails.
    """
    if not session_name or not os.environ.get("TMUX"):
        return

    # Potential targets to try in order of specificity
    targets = [session_name]

    # If session_name has an underscore, it might be a session_pane separator we added.
    # Try the prefix as a session name fallback.
    if "_" in session_name and not session_name.startswith("%"):
        targets.append(session_name.rsplit("_", 1)[0])

    # If we have TMUX env var, it's a comma-separated list: socket_path,pid,session_index
    # We use the socket path to ensure we target the correct tmux server instance.
    tmux_env = os.environ.get("TMUX", "")
    socket_path = tmux_env.split(",")[0] if tmux_env else None

    for t in targets:
        try:
            # We use 'tmux switch-client' which is the standard way to switch sessions/panes.
            # It works for sessions, windows, and panes (via %ID).
            cmd = ["tmux"]
            if socket_path:
                cmd.extend(["-S", socket_path])
            cmd.extend(["switch-client", "-t", t])

            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                return  # Success!
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
        except Exception as e:
            import sys

            print(
                f"Unexpected error switching to tmux session '{session_name}': {e}",
                file=sys.stderr,
            )
            break
