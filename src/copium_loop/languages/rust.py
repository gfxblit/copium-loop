import os

from .base import Command, CompositeCommand, LanguageStrategy


class RustStrategy(LanguageStrategy):
    @property
    def name(self) -> str:
        return "rust"

    def match(self, path: str) -> bool:
        return os.path.exists(os.path.normpath(os.path.join(path, "Cargo.toml")))

    def get_test_command(self, path: str) -> Command | CompositeCommand | None:
        return Command("cargo", ["test"], cwd=None if path == "." else path)

    def get_build_command(self, path: str) -> Command | CompositeCommand | None:
        return Command("cargo", ["build"], cwd=None if path == "." else path)

    def get_lint_command(self, path: str) -> Command | CompositeCommand | None:
        cwd = None if path == "." else path
        return CompositeCommand(
            commands=[
                Command("cargo", ["clippy"], cwd=cwd),
                Command("cargo", ["fmt", "--check"], cwd=cwd),
            ]
        )
