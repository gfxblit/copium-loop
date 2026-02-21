import subprocess
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CommandRunner(Protocol):
    def run(
        self, args: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[Any]: ...


@runtime_checkable
class TmuxInterface(Protocol):
    def list_windows(self, session: str) -> list[str]: ...

    def has_window(self, session: str, window: str) -> bool: ...

    def new_window(self, session: str, window: str, command: str): ...

    def send_keys(self, target: str, keys: str | list[str]): ...

    def capture_pane(self, target: str) -> str: ...


class SubprocessRunner:
    def run(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        return subprocess.run(args, **kwargs)


class TmuxManager:
    def __init__(self, runner: CommandRunner | None = None):
        self.runner = runner or SubprocessRunner()

    def list_windows(self, session: str) -> list[str]:
        result = self.runner.run(
            ["tmux", "list-windows", "-t", session, "-F", "#{window_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return []
        return result.stdout.splitlines()

    def has_window(self, session: str, window: str) -> bool:
        windows = self.list_windows(session)
        return window in windows

    def new_window(self, session: str, window: str, command: str):
        self.runner.run(
            ["tmux", "new-window", "-t", session, "-n", window, "-d", command],
            capture_output=True,
            text=True,
            check=False,
        )

    def send_keys(self, target: str, keys: str | list[str]):
        if isinstance(keys, str):
            keys = [keys]
        self.runner.run(
            ["tmux", "send-keys", "-t", target] + keys,
            check=False,
        )

    def capture_pane(self, target: str) -> str:
        result = self.runner.run(
            ["tmux", "capture-pane", "-p", "-t", target],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return ""
        return result.stdout
