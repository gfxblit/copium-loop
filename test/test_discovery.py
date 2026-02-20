import os
from unittest.mock import patch

import pytest

from copium_loop import discovery


def test_get_test_command_pytest():
    """Test that get_test_command returns pytest for python projects."""

    def side_effect(path):
        return path == "pyproject.toml"

    with patch("os.path.exists", side_effect=side_effect):
        cmd, args = discovery.get_test_command()
        assert cmd == "pytest"
        assert "--cov=src" in args
        assert "--cov-report=term-missing" in args
        assert "--cov-fail-under=80" in args


def test_get_test_command_pytest_custom_coverage():
    """Test that get_test_command respects COPIUM_MIN_COVERAGE."""

    def side_effect(path):
        return path == "pyproject.toml"

    with (
        patch("os.path.exists", side_effect=side_effect),
        patch.dict("os.environ", {"COPIUM_MIN_COVERAGE": "90"}),
    ):
        cmd, args = discovery.get_test_command()
        assert cmd == "pytest"
        assert "--cov-fail-under=90" in args


def test_get_test_command_npm_priority():
    """Test that get_test_command returns npm if package.json exists, even if pyproject.toml exists."""

    def side_effect(path):
        return path in ["package.json", "pyproject.toml", "package-lock.json"]

    with patch("os.path.exists", side_effect=side_effect):
        cmd, args = discovery.get_test_command()
        assert cmd == "npm"
        assert args == ["test"]


def test_get_package_manager_detection():
    """Test detection of different package managers."""
    # Test npm (default)
    with patch("os.path.exists", return_value=False):
        assert discovery.get_package_manager() == "npm"

    # Test pnpm
    def pnpm_side_effect(path):
        return path == "pnpm-lock.yaml"

    with patch("os.path.exists", side_effect=pnpm_side_effect):
        assert discovery.get_package_manager() == "pnpm"

    # Test yarn
    def yarn_side_effect(path):
        return path == "yarn.lock"

    with patch("os.path.exists", side_effect=yarn_side_effect):
        assert discovery.get_package_manager() == "yarn"


def test_get_test_command_pnpm_priority():
    """Test that get_test_command returns pnpm if package.json and pnpm-lock.yaml exist."""

    def side_effect(path):
        return path in ["package.json", "pnpm-lock.yaml"]

    with patch("os.path.exists", side_effect=side_effect):
        cmd, args = discovery.get_test_command()
        assert cmd == "pnpm"
        assert args == ["test"]


def test_get_lint_command_ruff():
    """Test that get_lint_command returns ruff for python projects."""

    def side_effect(path):
        return path == "pyproject.toml"

    with patch("os.path.exists", side_effect=side_effect):
        cmd, args = discovery.get_lint_command()
        assert cmd == "sh"
        assert args == ["-c", "ruff check . && ruff format --check ."]


def test_get_lint_command_npm_priority():
    """Test that get_lint_command returns npm if package.json exists, even if pyproject.toml exists."""

    def side_effect(path):
        return path in ["package.json", "pyproject.toml"]

    with patch("os.path.exists", side_effect=side_effect):
        cmd, args = discovery.get_lint_command()
        assert cmd == "npm"
        assert args == ["run", "lint"]


def test_get_test_command_env_override():
    """Test that get_test_command respects COPIUM_TEST_CMD environment variable."""
    with patch.dict("os.environ", {"COPIUM_TEST_CMD": "mytest --fast"}):
        cmd, args = discovery.get_test_command()
        assert cmd == "mytest"
        assert args == ["--fast"]


def test_get_build_command_npm():
    """Test that get_build_command returns npm for node projects."""
    with (
        patch("os.path.exists", return_value=True),
        patch("copium_loop.discovery.get_package_manager", return_value="npm"),
    ):
        cmd, args = discovery.get_build_command()
        assert cmd == "npm"
        assert args == ["run", "build"]


def test_get_build_command_env_override():
    """Test that get_build_command respects COPIUM_BUILD_CMD environment variable."""
    with patch.dict("os.environ", {"COPIUM_BUILD_CMD": "mybuild --prod"}):
        cmd, args = discovery.get_build_command()
        assert cmd == "mybuild"
        assert args == ["--prod"]


def test_get_build_command_python_empty():
    """Test that get_build_command returns empty for python projects without explicit build."""

    def side_effect(path):
        return path == "pyproject.toml"

    with patch("os.path.exists", side_effect=side_effect):
        cmd, args = discovery.get_build_command()
        assert cmd == ""
        assert args == []


def test_get_lint_command_env_override():
    """Test that get_lint_command respects COPIUM_LINT_CMD environment variable."""
    with patch.dict("os.environ", {"COPIUM_LINT_CMD": "mylint --strict"}):
        cmd, args = discovery.get_lint_command()
        assert cmd == "mylint"
        assert args == ["--strict"]


def test_get_lint_command_python_no_config():
    """Test that get_lint_command returns ruff for python projects even if no config file exists."""

    def side_effect(path):
        # No standard config files, but some .py file exists
        if path in ["pyproject.toml", "setup.py", "requirements.txt", "package.json"]:
            return False
        return path.endswith(".py")

    class MockEntry:
        def __init__(self, name):
            self.name = name
            self.is_file_val = True

        def is_file(self):
            return self.is_file_val

    with (
        patch("os.path.exists", side_effect=side_effect),
        patch("os.scandir", return_value=[MockEntry("main.py")]),
    ):
        cmd, args = discovery.get_lint_command()
        assert cmd == "sh"
        assert args == ["-c", "ruff check . && ruff format --check ."]


@pytest.mark.parametrize(
    "file_to_create", ["pyproject.toml", "setup.py", "requirements.txt", "main.py"]
)
def test_discovery_python_project_detection(file_to_create, tmp_path):
    """Test that python projects are detected correctly with various files."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        if file_to_create == "main.py":
            (tmp_path / "main.py").touch()
        else:
            (tmp_path / file_to_create).touch()

        test_cmd, _ = discovery.get_test_command()
        assert test_cmd == "pytest"

        build_cmd, _ = discovery.get_build_command()
        assert build_cmd == ""

        lint_cmd, _ = discovery.get_lint_command()
        assert lint_cmd == "sh"
    finally:
        os.chdir(original_cwd)


def test_discovery_no_python_project(tmp_path):
    """Test that non-python projects (without package.json) default to npm."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Empty directory
        test_cmd, _ = discovery.get_test_command()
        assert test_cmd == "npm"
    finally:
        os.chdir(original_cwd)
