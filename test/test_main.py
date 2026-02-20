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
    # Note: The exact error message might change during implementation, but it should contain "invalid start node"
    assert (
        "Invalid start node" in result.stdout or "Invalid start node" in result.stderr
    )
    assert "Valid nodes are:" in result.stdout or "Valid nodes are:" in result.stderr


def test_readme_mentions_monitor_flag():
    """Verify README mentions the --monitor flag."""
    with open("README.md") as f:
        content = f.read()
    assert "--monitor" in content or "-m " in content or " -m" in content


def test_readme_mentions_continue_flag():
    """Verify README mentions the --continue flag."""
    with open("README.md") as f:
        content = f.read()
    assert "--continue" in content or " -c" in content


def test_readme_mentions_session_flag():
    """Verify README mentions the --session flag."""
    with open("README.md") as f:
        content = f.read()
    assert "--session" in content


def test_readme_mentions_python_support():
    """Verify README mentions Python/pytest support in 'How It Works' or 'Usage'."""
    with open("README.md") as f:
        content = f.read()
    # Check if it mentions pytest in the context of automatic detection
    assert "pytest" in content.lower() and "detect" in content.lower()


def test_readme_mentions_custom_commands():
    """Verify README mentions custom command environment variables."""
    with open("README.md") as f:
        content = f.read()
    assert "COPIUM_TEST_CMD" in content or "custom commands" in content.lower()


def test_readme_mentions_issue_linking():
    """Verify README mentions automatic GitHub issue linking."""
    with open("README.md") as f:
        content = f.read()
    assert "issue" in content.lower() and (
        "link" in content.lower() or "refer" in content.lower()
    )


def test_readme_mentions_dashboard():
    """Verify README mentions the multi-session monitor/dashboard."""
    with open("README.md") as f:
        content = f.read()
    assert "monitor" in content.lower() or "dashboard" in content.lower()
