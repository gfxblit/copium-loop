import os

from copium_loop.languages import (
    Command,
    CompositeCommand,
    LanguageStrategy,
    NodeStrategy,
    PythonStrategy,
    RustStrategy,
)

# Global registry for language strategies
_strategies: list[LanguageStrategy] = [
    NodeStrategy(),
    RustStrategy(),
    PythonStrategy(),
]


def register_strategy(strategy: LanguageStrategy) -> None:
    """Register a new language strategy."""
    _strategies.append(strategy)


def unregister_strategy(name: str) -> None:
    """Unregister a language strategy by name."""
    global _strategies
    _strategies = [s for s in _strategies if s.name != name]


def _get_project_strategy(path: str) -> LanguageStrategy | None:
    for strategy in _strategies:
        if strategy.match(path):
            return strategy
    return None


def _discover_projects() -> list[tuple[str, LanguageStrategy]]:
    projects = []
    root_strategy = _get_project_strategy(".")
    if root_strategy:
        projects.append((".", root_strategy))

    try:
        for f in os.scandir("."):
            if (
                f.is_dir()
                and not f.name.startswith(".")
                and f.name
                not in ["node_modules", "venv", ".venv", "target", "test", "tests"]
            ):
                strategy = _get_project_strategy(f.path)
                if strategy:
                    projects.append((f.path, strategy))
    except OSError:
        pass

    return projects


def _get_composite_command(
    projects: list[tuple[str, LanguageStrategy]],
    cmd_type: str,
) -> Command | CompositeCommand | None:
    all_commands = []
    for path, strategy in projects:
        cmd = None
        if cmd_type == "test":
            cmd = strategy.get_test_command(path)
        elif cmd_type == "build":
            cmd = strategy.get_build_command(path)
        elif cmd_type == "lint":
            cmd = strategy.get_lint_command(path)

        if cmd:
            if isinstance(cmd, CompositeCommand):
                all_commands.extend(cmd.commands)
            else:
                all_commands.append(cmd)

    if not all_commands:
        return None

    if len(all_commands) == 1:
        return all_commands[0]

    return CompositeCommand(commands=all_commands)


def get_test_command() -> Command | CompositeCommand:
    """Determines the test command based on the project structure."""
    if os.environ.get("COPIUM_TEST_CMD"):
        parts = os.environ.get("COPIUM_TEST_CMD").split()
        return Command(executable=parts[0], args=parts[1:])

    projects = _discover_projects()
    cmd = _get_composite_command(projects, "test")

    if not projects:
        return Command(executable="npm", args=["test"])

    return cmd


def get_build_command() -> Command | CompositeCommand | None:
    """Determines the build command based on the project structure."""
    if os.environ.get("COPIUM_BUILD_CMD"):
        parts = os.environ.get("COPIUM_BUILD_CMD").split()
        return Command(executable=parts[0], args=parts[1:])

    projects = _discover_projects()
    cmd = _get_composite_command(projects, "build")

    if not projects:
        return Command(executable="npm", args=["run", "build"])

    return cmd


def get_lint_command() -> Command | CompositeCommand:
    """Determines the lint command based on the project structure."""
    if os.environ.get("COPIUM_LINT_CMD"):
        parts = os.environ.get("COPIUM_LINT_CMD").split()
        return Command(executable=parts[0], args=parts[1:])

    projects = _discover_projects()
    cmd = _get_composite_command(projects, "lint")

    if not projects:
        return Command(executable="npm", args=["run", "lint"])

    return cmd
