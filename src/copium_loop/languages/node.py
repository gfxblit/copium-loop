import os

from .base import Command, CompositeCommand, LanguageStrategy


def get_package_manager(path: str = ".") -> str:
    """Detects the package manager based on lock files."""
    pnpm_lock = os.path.normpath(os.path.join(path, "pnpm-lock.yaml"))
    yarn_lock = os.path.normpath(os.path.join(path, "yarn.lock"))
    if os.path.exists(pnpm_lock):
        return "pnpm"
    if os.path.exists(yarn_lock):
        return "yarn"
    return "npm"


class NodeStrategy(LanguageStrategy):
    @property
    def name(self) -> str:
        return "node"

    def match(self, path: str) -> bool:
        return os.path.exists(os.path.normpath(os.path.join(path, "package.json")))

    def get_test_command(self, path: str) -> Command | CompositeCommand | None:
        pm = get_package_manager(path)
        return Command(pm, ["test"], cwd=None if path == "." else path)

    def get_build_command(self, path: str) -> Command | CompositeCommand | None:
        pm = get_package_manager(path)
        return Command(pm, ["run", "build"], cwd=None if path == "." else path)

    def get_lint_command(self, path: str) -> Command | CompositeCommand | None:
        pm = get_package_manager(path)
        return Command(pm, ["run", "lint"], cwd=None if path == "." else path)
