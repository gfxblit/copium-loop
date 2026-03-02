from copium_loop.languages.base import Command, CompositeCommand
from copium_loop.languages.node import NodeStrategy
from copium_loop.languages.python import PythonStrategy
from copium_loop.languages.rust import RustStrategy


def test_command_to_shell_args():
    cmd = Command("npm", ["test"])
    assert cmd.executable == "npm"
    assert cmd.args == ["test"]


def test_node_strategy_match(tmp_path):
    strategy = NodeStrategy()
    (tmp_path / "package.json").touch()
    assert strategy.match(str(tmp_path))
    assert not strategy.match(str(tmp_path / "other"))


def test_rust_strategy_match(tmp_path):
    strategy = RustStrategy()
    (tmp_path / "Cargo.toml").touch()
    assert strategy.match(str(tmp_path))


def test_python_strategy_match(tmp_path):
    strategy = PythonStrategy()
    (tmp_path / "pyproject.toml").touch()
    assert strategy.match(str(tmp_path))

    (tmp_path / "pyproject.toml").unlink()
    (tmp_path / "main.py").touch()
    assert strategy.match(str(tmp_path))


def test_node_strategy_commands():
    strategy = NodeStrategy()
    cmd = strategy.get_test_command(".")
    assert cmd.executable == "npm"
    assert cmd.args == ["test"]

    cmd = strategy.get_build_command(".")
    assert cmd.executable == "npm"
    assert cmd.args == ["run", "build"]


def test_rust_strategy_commands():
    strategy = RustStrategy()
    cmd = strategy.get_test_command(".")
    assert cmd.executable == "cargo"
    assert cmd.args == ["test"]

    cmd = strategy.get_lint_command(".")
    assert isinstance(cmd, CompositeCommand)
    assert len(cmd.commands) == 2
    assert cmd.commands[0].executable == "cargo"
    assert cmd.commands[0].args == ["clippy"]
    assert cmd.commands[1].executable == "cargo"
    assert cmd.commands[1].args == ["fmt", "--check"]
