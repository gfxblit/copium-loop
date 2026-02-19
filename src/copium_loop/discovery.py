import glob
import os

from copium_loop.constants import DEFAULT_MIN_COVERAGE


def get_package_manager() -> str:
    """Detects the package manager based on lock files."""
    if os.path.exists("pnpm-lock.yaml"):
        return "pnpm"
    if os.path.exists("yarn.lock"):
        return "yarn"
    return "npm"


def _is_python_project() -> bool:
    """Checks if the current directory is a Python project."""
    return (
        os.path.exists("pyproject.toml")
        or os.path.exists("setup.py")
        or os.path.exists("requirements.txt")
        or any(glob.glob("*.py"))
    )


def get_test_command() -> tuple[str, list[str]]:
    """Determines the test command based on the project structure."""
    test_cmd = "npm"
    test_args = ["test"]

    if os.environ.get("COPIUM_TEST_CMD"):
        parts = os.environ.get("COPIUM_TEST_CMD").split()
        test_cmd = parts[0]
        test_args = parts[1:]
    elif os.path.exists("package.json"):
        test_cmd = get_package_manager()
        test_args = ["test"]
    elif _is_python_project():
        min_cov = os.environ.get("COPIUM_MIN_COVERAGE", str(DEFAULT_MIN_COVERAGE))
        test_cmd = "pytest"
        test_args = [
            "--cov=src",
            "--cov-report=term-missing",
            f"--cov-fail-under={min_cov}",
        ]

    return test_cmd, test_args


def get_build_command() -> tuple[str, list[str]]:
    """Determines the build command based on the project structure."""
    build_cmd = "npm"
    build_args = ["run", "build"]

    if os.environ.get("COPIUM_BUILD_CMD"):
        parts = os.environ.get("COPIUM_BUILD_CMD").split()
        build_cmd = parts[0]
        build_args = parts[1:]
    elif os.path.exists("package.json"):
        build_cmd = get_package_manager()
        build_args = ["run", "build"]
    elif _is_python_project():
        return "", []

    return build_cmd, build_args


def get_lint_command() -> tuple[str, list[str]]:
    """Determines the lint command based on the project structure."""
    lint_cmd = "npm"
    lint_args = ["run", "lint"]

    if os.environ.get("COPIUM_LINT_CMD"):
        parts = os.environ.get("COPIUM_LINT_CMD").split()
        lint_cmd = parts[0]
        lint_args = parts[1:]
    elif os.path.exists("package.json"):
        lint_cmd = get_package_manager()
        lint_args = ["run", "lint"]
    elif _is_python_project():
        lint_cmd = "sh"
        lint_args = ["-c", "ruff check . && ruff format --check ."]

    return lint_cmd, lint_args
