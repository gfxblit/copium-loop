import os

from copium_loop.constants import DEFAULT_MIN_COVERAGE


def get_package_manager(path: str = ".") -> str:
    """Detects the package manager based on lock files."""
    pnpm_lock = (
        "pnpm-lock.yaml" if path == "." else os.path.join(path, "pnpm-lock.yaml")
    )
    yarn_lock = "yarn.lock" if path == "." else os.path.join(path, "yarn.lock")
    if os.path.exists(pnpm_lock):
        return "pnpm"
    if os.path.exists(yarn_lock):
        return "yarn"
    return "npm"


def _get_project_type(path: str) -> str | None:
    def check(name):
        return os.path.exists(name if path == "." else os.path.join(path, name))

    if check("package.json"):
        return "node"
    if check("Cargo.toml"):
        return "rust"

    py_indicators = ["pyproject.toml", "setup.py", "requirements.txt"]
    for ind in py_indicators:
        if check(ind):
            return "python"

    # Only fallback to checking .py files for the root directory,
    # or if we are dealing with a path that specifically has no other indicators
    # but we want to avoid false-positives for sub-packages.
    if path == ".":
        try:
            if os.path.isdir(path):
                for f in os.scandir(path):
                    if f.is_file() and f.name.endswith(".py"):
                        return "python"
        except OSError:
            pass
    return None


def _discover_projects() -> list[tuple[str, str]]:
    projects = []
    root_type = _get_project_type(".")
    if root_type:
        projects.append((".", root_type))

    try:
        for f in os.scandir("."):
            if (
                f.is_dir()
                and not f.name.startswith(".")
                and f.name not in ["node_modules", "venv", ".venv", "target"]
            ):
                ptype = _get_project_type(f.path)
                if ptype:
                    projects.append((f.path, ptype))
    except OSError:
        pass

    return projects


def _get_commands_for_project(path: str, ptype: str, cmd_type: str) -> str | None:
    if ptype == "node":
        pm = get_package_manager(path)
        commands = {
            "test": f"{pm} test",
            "build": f"{pm} run build",
            "lint": f"{pm} run lint",
        }
        return commands.get(cmd_type)
    elif ptype == "rust":
        commands = {
            "test": "cargo test",
            "build": "cargo build",
            "lint": "cargo clippy && cargo fmt --check",
        }
        return commands.get(cmd_type)
    elif ptype == "python":
        min_cov = os.environ.get("COPIUM_MIN_COVERAGE", str(DEFAULT_MIN_COVERAGE))
        commands = {
            "test": f"pytest --cov=src --cov-report=term-missing --cov-fail-under={min_cov}",
            "build": None,
            "lint": "ruff check . && ruff format --check .",
        }
        return commands.get(cmd_type)
    return None


def _build_composite_command(
    projects: list[tuple[str, str]],
    cmd_type: str,
    default_cmd: str,
    default_args: list[str],
) -> tuple[str, list[str]]:
    commands = []
    for path, ptype in projects:
        cmd_str = _get_commands_for_project(path, ptype, cmd_type)
        if cmd_str:
            if path == ".":
                commands.append(f"({cmd_str})")
            else:
                # Strip leading './' if present for cleaner output
                clean_path = path[2:] if path.startswith("./") else path
                commands.append(f"(cd {clean_path} && {cmd_str})")

    if not commands:
        if (
            projects
            and len(projects) == 1
            and projects[0][1] == "python"
            and cmd_type == "build"
        ):
            return "", []
        return default_cmd, default_args

    if len(commands) == 1 and projects[0][0] == ".":
        # Single root project, maintain backward compatibility
        parts = commands[0][1:-1].split(" ")  # remove parenthesis
        cmd_str = commands[0][1:-1]
        if "&&" in cmd_str or cmd_str.startswith("pytest --cov="):
            if "&&" in cmd_str:
                return "sh", ["-c", cmd_str]
            else:
                parts = cmd_str.split(" ")
                return parts[0], parts[1:]

        return parts[0], parts[1:]

    return "sh", ["-c", " && ".join(commands)]


def get_test_command() -> tuple[str, list[str]]:
    """Determines the test command based on the project structure."""
    if os.environ.get("COPIUM_TEST_CMD"):
        parts = os.environ.get("COPIUM_TEST_CMD").split()
        return parts[0], parts[1:]

    projects = _discover_projects()
    if not projects:
        return "npm", ["test"]

    return _build_composite_command(projects, "test", "npm", ["test"])


def get_build_command() -> tuple[str, list[str]]:
    """Determines the build command based on the project structure."""
    if os.environ.get("COPIUM_BUILD_CMD"):
        parts = os.environ.get("COPIUM_BUILD_CMD").split()
        return parts[0], parts[1:]

    projects = _discover_projects()
    if not projects:
        return "npm", ["run", "build"]

    return _build_composite_command(projects, "build", "npm", ["run", "build"])


def get_lint_command() -> tuple[str, list[str]]:
    """Determines the lint command based on the project structure."""
    if os.environ.get("COPIUM_LINT_CMD"):
        parts = os.environ.get("COPIUM_LINT_CMD").split()
        return parts[0], parts[1:]

    projects = _discover_projects()
    if not projects:
        return "npm", ["run", "lint"]

    return _build_composite_command(projects, "lint", "npm", ["run", "lint"])
