import os

from copium_loop.constants import DEFAULT_MIN_COVERAGE

from .base import Command, CompositeCommand, LanguageStrategy


class PythonStrategy(LanguageStrategy):
    @property
    def name(self) -> str:
        return "python"

    def match(self, path: str) -> bool:
        py_indicators = ["pyproject.toml", "setup.py", "requirements.txt"]
        for ind in py_indicators:
            if os.path.exists(ind if path == "." else os.path.join(path, ind)):
                return True

        # Check for any .py files in the directory
        try:
            target_dir = path if path != "." else "."
            if os.path.isdir(target_dir):
                for f in os.scandir(target_dir):
                    if f.is_file() and f.name.endswith(".py"):
                        return True
        except OSError:
            pass
        return False

    def get_test_command(self, path: str) -> Command | CompositeCommand | None:
        min_cov = os.environ.get("COPIUM_MIN_COVERAGE", str(DEFAULT_MIN_COVERAGE))
        cwd = None if path == "." else path
        return Command(
            "pytest",
            [
                "--cov=src",
                "--cov-report=term-missing",
                f"--cov-fail-under={min_cov}",
            ],
            cwd=cwd,
        )

    def get_build_command(self, _path: str) -> Command | CompositeCommand | None:
        return None

    def get_lint_command(self, path: str) -> Command | CompositeCommand | None:
        cwd = None if path == "." else path
        return CompositeCommand(
            commands=[
                Command("ruff", ["check", "."], cwd=cwd),
                Command("ruff", ["format", "--check", "."], cwd=cwd),
            ]
        )
