import os
from unittest.mock import patch

import pytest

from copium_loop import discovery
from copium_loop.languages import CompositeCommand


def test_get_test_command_pytest():
    """Test that get_test_command returns pytest for python projects."""

    def side_effect(path):
        return path == "pyproject.toml"

    with patch("os.path.exists", side_effect=side_effect):
        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "pytest"
        assert "--cov=src" in cmd_obj.args
        assert "--cov-report=term-missing" in cmd_obj.args
        assert "--cov-fail-under=80" in cmd_obj.args


def test_get_test_command_pytest_custom_coverage():
    """Test that get_test_command respects COPIUM_MIN_COVERAGE."""

    def side_effect(path):
        return path == "pyproject.toml"

    with (
        patch("os.path.exists", side_effect=side_effect),
        patch.dict("os.environ", {"COPIUM_MIN_COVERAGE": "90"}),
    ):
        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "pytest"
        assert "--cov-fail-under=90" in cmd_obj.args


def test_get_test_command_npm_priority():
    """Test that get_test_command returns npm if package.json exists, even if pyproject.toml exists."""

    def side_effect(path):
        return path in ["package.json", "pyproject.toml", "package-lock.json"]

    with patch("os.path.exists", side_effect=side_effect):
        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "npm"
        assert cmd_obj.args == ["test"]


def test_get_package_manager_detection():
    """Test detection of different package managers."""
    from copium_loop.languages.node import get_package_manager

    # Test npm (default)
    with patch("os.path.exists", return_value=False):
        assert get_package_manager() == "npm"

    # Test pnpm
    def pnpm_side_effect(path):
        return path == "pnpm-lock.yaml"

    with patch("os.path.exists", side_effect=pnpm_side_effect):
        assert get_package_manager() == "pnpm"

    # Test yarn
    def yarn_side_effect(path):
        return path == "yarn.lock"

    with patch("os.path.exists", side_effect=yarn_side_effect):
        assert get_package_manager() == "yarn"


def test_get_test_command_pnpm_priority():
    """Test that get_test_command returns pnpm if package.json and pnpm-lock.yaml exist."""

    def side_effect(path):
        return path in ["package.json", "pnpm-lock.yaml"]

    with patch("os.path.exists", side_effect=side_effect):
        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "pnpm"
        assert cmd_obj.args == ["test"]


def test_get_lint_command_ruff():
    """Test that get_lint_command returns ruff for python projects."""

    def side_effect(path):
        return path == "pyproject.toml"

    with patch("os.path.exists", side_effect=side_effect):
        cmd_obj = discovery.get_lint_command()
        # Ruff lint is now a CompositeCommand
        assert cmd_obj.commands[0].executable == "ruff"
        assert cmd_obj.commands[0].args == ["check", "."]


def test_get_lint_command_npm_priority():
    """Test that get_lint_command returns npm if package.json exists, even if pyproject.toml exists."""

    def side_effect(path):
        return path in ["package.json", "pyproject.toml"]

    with patch("os.path.exists", side_effect=side_effect):
        cmd_obj = discovery.get_lint_command()
        assert cmd_obj.executable == "npm"
        assert cmd_obj.args == ["run", "lint"]


def test_get_test_command_env_override():
    """Test that get_test_command respects COPIUM_TEST_CMD environment variable."""
    with patch.dict("os.environ", {"COPIUM_TEST_CMD": "mytest --fast"}):
        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "mytest"
        assert cmd_obj.args == ["--fast"]


def test_get_build_command_npm():
    """Test that get_build_command returns npm for node projects."""

    def side_effect(path):
        return "lock" not in path

    with (
        patch("os.path.exists", side_effect=side_effect),
        patch("os.scandir", return_value=[]),
    ):
        cmd_obj = discovery.get_build_command()
        assert cmd_obj.executable == "npm"
        assert cmd_obj.args == ["run", "build"]


def test_get_build_command_env_override():
    """Test that get_build_command respects COPIUM_BUILD_CMD environment variable."""
    with patch.dict("os.environ", {"COPIUM_BUILD_CMD": "mybuild --prod"}):
        cmd_obj = discovery.get_build_command()
        assert cmd_obj.executable == "mybuild"
        assert cmd_obj.args == ["--prod"]


def test_get_build_command_python_empty():
    """Test that get_build_command returns None for python projects without explicit build."""

    def side_effect(path):
        return path == "pyproject.toml"

    with patch("os.path.exists", side_effect=side_effect):
        cmd_obj = discovery.get_build_command()
        assert cmd_obj is None


def test_get_lint_command_env_override():
    """Test that get_lint_command respects COPIUM_LINT_CMD environment variable."""
    with patch.dict("os.environ", {"COPIUM_LINT_CMD": "mylint --strict"}):
        cmd_obj = discovery.get_lint_command()
        assert cmd_obj.executable == "mylint"
        assert cmd_obj.args == ["--strict"]


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
        cmd_obj = discovery.get_lint_command()
        assert cmd_obj.commands[0].executable == "ruff"


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

        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "pytest"

        cmd_obj = discovery.get_build_command()
        assert cmd_obj is None

        cmd_obj = discovery.get_lint_command()
        assert isinstance(cmd_obj, CompositeCommand)
    finally:
        os.chdir(original_cwd)


def test_discovery_no_python_project(tmp_path):
    """Test that non-python projects (without package.json) default to npm."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        # Empty directory
        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "npm"
    finally:
        os.chdir(original_cwd)


def test_discovery_rust_only(tmp_path):
    """Test that rust projects are detected correctly with Cargo.toml."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "Cargo.toml").touch()

        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "cargo"
        assert cmd_obj.args == ["test"]

        cmd_obj = discovery.get_build_command()
        assert cmd_obj.executable == "cargo"
        assert cmd_obj.args == ["build"]

        cmd_obj = discovery.get_lint_command()
        assert isinstance(cmd_obj, CompositeCommand)
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

        test_cmd = discovery.get_test_command()
        assert isinstance(test_cmd, CompositeCommand)
        cmd_strs = [str(c) for c in test_cmd.commands]
        assert any("client" in s and "npm test" in s for s in cmd_strs)
        assert any("server" in s and "cargo test" in s for s in cmd_strs)
        assert any("pytest" in s for s in cmd_strs)

        build_cmd = discovery.get_build_command()
        assert isinstance(build_cmd, CompositeCommand)
        cmd_strs = [str(c) for c in build_cmd.commands]
        assert any("client" in s and "npm run build" in s for s in cmd_strs)
        assert any("server" in s and "cargo build" in s for s in cmd_strs)

        lint_cmd = discovery.get_lint_command()
        assert isinstance(lint_cmd, CompositeCommand)
        cmd_strs = [str(c) for c in lint_cmd.commands]
        assert any("client" in s and "npm run lint" in s for s in cmd_strs)
        assert any("server" in s and "cargo clippy" in s for s in cmd_strs)
        assert any("ruff" in s for s in cmd_strs)

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

        # Build command should be None for a pure python monorepo
        cmd_obj = discovery.get_build_command()
        assert cmd_obj is None
    finally:
        os.chdir(original_cwd)


class MockGoStrategy:
    @property
    def name(self) -> str:
        return "go"

    def match(self, path: str) -> bool:
        return os.path.exists("go.mod" if path == "." else os.path.join(path, "go.mod"))

    def get_test_command(self, _path: str):
        from copium_loop.languages import Command

        return Command("go", ["test", "./..."])

    def get_build_command(self, _path: str):
        from copium_loop.languages import Command

        return Command("go", ["build", "./..."])

    def get_lint_command(self, _path: str):
        from copium_loop.languages import Command

        return Command("golangci-lint", ["run"])


def test_custom_language_strategy(tmp_path):
    """Test that a custom language strategy can be registered and used."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        (tmp_path / "go.mod").touch()

        # Register custom strategy
        discovery.register_strategy(MockGoStrategy())

        cmd_obj = discovery.get_test_command()
        assert cmd_obj.executable == "go"
        assert cmd_obj.args == ["test", "./..."]

        # Clean up registration
        discovery.unregister_strategy("go")
    finally:
        os.chdir(original_cwd)
