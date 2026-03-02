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
        patch("os.scandir", return_value=[]),
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

    from unittest.mock import MagicMock

    mock_entry = MagicMock()
    mock_entry.name = "main.py"
    mock_entry.is_file.return_value = True
    mock_entry.is_dir.return_value = False

    with (
        patch("os.path.exists", side_effect=side_effect),
        patch("os.scandir", return_value=[mock_entry]),
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


def test_discovery_rust_only(tmp_path):
    """Test that rust projects are detected correctly with Cargo.toml."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "Cargo.toml").touch()

        test_cmd, test_args = discovery.get_test_command()
        assert test_cmd == "cargo"
        assert test_args == ["test"]

        build_cmd, build_args = discovery.get_build_command()
        assert build_cmd == "cargo"
        assert build_args == ["build"]

        lint_cmd, lint_args = discovery.get_lint_command()
        assert lint_cmd == "sh"
        assert lint_args == ["-c", "cargo clippy && cargo fmt --check"]
    finally:
        os.chdir(original_cwd)


def test_discovery_hybrid_project(tmp_path):
    """Test hybrid project discovery."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Create client node project
        client_dir = tmp_path / "client"
        client_dir.mkdir()
        (client_dir / "package.json").touch()

        # Create server rust project
        server_dir = tmp_path / "server"
        server_dir.mkdir()
        (server_dir / "Cargo.toml").touch()

        # Create root python project
        (tmp_path / "pyproject.toml").touch()

        test_cmd, test_args = discovery.get_test_command()
        assert test_cmd == "sh"
        assert test_args[0] == "-c"
        command_str = test_args[1]
        assert "(cd client && npm test)" in command_str
        assert "(cd server && cargo test)" in command_str
        assert "pytest" in command_str

        build_cmd, build_args = discovery.get_build_command()
        assert build_cmd == "sh"
        assert build_args[0] == "-c"
        command_str = build_args[1]
        assert "(cd client && npm run build)" in command_str
        assert "(cd server && cargo build)" in command_str
        assert "pytest" not in command_str

        lint_cmd, lint_args = discovery.get_lint_command()
        assert lint_cmd == "sh"
        assert lint_args[0] == "-c"
        command_str = lint_args[1]
        assert "(cd client && npm run lint)" in command_str
        assert "(cd server && cargo clippy && cargo fmt --check)" in command_str
        assert "ruff check . && ruff format --check ." in command_str
    finally:
        os.chdir(original_cwd)


def test_discovery_python_monorepo_build(tmp_path):
    """Test that python monorepos do not incorrectly fallback to npm build."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Create root python project
        (tmp_path / "pyproject.toml").touch()

        # Create sub-package python project
        sub_dir = tmp_path / "tests"
        sub_dir.mkdir()
        (sub_dir / "requirements.txt").touch()

        # Build command should be empty for a pure python monorepo
        build_cmd, build_args = discovery.get_build_command()
        assert build_cmd == ""
        assert build_args == []
    finally:
        os.chdir(original_cwd)
