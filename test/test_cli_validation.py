import subprocess
import sys


def test_cli_invalid_start_node():
    """
    Test that the CLI fails with a non-zero exit code and prints an error message
    when an invalid start node is provided.
    """
    # Run the CLI command
    env = {"PYTHONPATH": "src"}
    result = subprocess.run(
        [sys.executable, "-m", "copium_loop", "-s", "invalid_node", "test prompt"],
        capture_output=True,
        text=True,
        env=env,
    )

    # Check exit code
    assert result.returncode != 0, (
        f"Expected non-zero exit code, got {result.returncode}"
    )

    # Check stderr for error message
    assert (
        "Invalid start node" in result.stdout or "Invalid start node" in result.stderr
    )
    assert "Valid nodes are:" in result.stdout or "Valid nodes are:" in result.stderr

def test_cli_invalid_engine():
    """
    Test that the CLI fails with a non-zero exit code when an invalid engine is provided.
    """
    env = {"PYTHONPATH": "src"}
    result = subprocess.run(
        [sys.executable, "-m", "copium_loop", "--engine", "invalid_engine", "test prompt"],
        capture_output=True,
        text=True,
        env=env,
    )

    # argparse will handle invalid choices and exit with code 2
    assert result.returncode != 0
    assert "invalid choice: 'invalid_engine'" in result.stderr
