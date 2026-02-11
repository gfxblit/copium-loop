import json
import os
import subprocess
from pathlib import Path

import pytest

from copium_loop.copium_loop import WorkflowManager


@pytest.fixture
def temp_repo(tmp_path):
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Save current directory
    old_cwd = os.getcwd()
    os.chdir(repo_dir)

    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"], check=True, capture_output=True
    )

    # Create a dummy pyproject.toml
    (repo_dir / "pyproject.toml").write_text(
        "[tool.pytest.ini_options]\ntestpaths = ['test']"
    )
    (repo_dir / "test").mkdir()

    # Initial commit is often needed
    (repo_dir / "README.md").write_text("# Test Repo")
    subprocess.run(["git", "add", "README.md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"], check=True, capture_output=True
    )
    subprocess.run(["git", "branch", "-M", "main"], check=True, capture_output=True)

    # Rename branch to main to ensure consistency
    subprocess.run(["git", "branch", "-M", "main"], check=True, capture_output=True)

    # Setup origin
    origin_dir = tmp_path / "origin"
    origin_dir.mkdir()
    subprocess.run(
        ["git", "init", "--bare"], cwd=origin_dir, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(origin_dir)],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)

    # Create and switch to feature branch
    subprocess.run(
        ["git", "checkout", "-b", "feature-branch"], check=True, capture_output=True
    )
    # Push feature branch to origin so it's tracked
    subprocess.run(
        ["git", "push", "-u", "origin", "feature-branch"],
        check=True,
        capture_output=True,
    )

    yield repo_dir

    os.chdir(old_cwd)


@pytest.fixture
def mock_bin(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    # Absolute path to cli_mock.py
    cli_mock_path = Path(__file__).parent.absolute() / "mocks" / "cli_mock.py"

    # Create symlinks
    (bin_dir / "gemini").symlink_to(cli_mock_path)
    (bin_dir / "gh").symlink_to(cli_mock_path)
    (bin_dir / "pytest").symlink_to(cli_mock_path)
    (bin_dir / "ruff").symlink_to(cli_mock_path)

    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{bin_dir}:{old_path}"

    # Set environment variables to use our mocks for discovery
    os.environ["COPIUM_TEST_CMD"] = "pytest"
    os.environ["COPIUM_LINT_CMD"] = "ruff"

    yield bin_dir

    os.environ["PATH"] = old_path
    if "COPIUM_TEST_CMD" in os.environ:
        del os.environ["COPIUM_TEST_CMD"]
    if "COPIUM_LINT_CMD" in os.environ:
        del os.environ["COPIUM_LINT_CMD"]


@pytest.fixture
def mock_instructions(tmp_path):
    instr_file = tmp_path / "instructions.json"
    os.environ["CLI_MOCK_INSTRUCTIONS"] = str(instr_file)
    yield instr_file
    if "CLI_MOCK_INSTRUCTIONS" in os.environ:
        del os.environ["CLI_MOCK_INSTRUCTIONS"]
    counter_file = instr_file.with_suffix(".counter")
    if counter_file.exists():
        counter_file.unlink()


@pytest.mark.usefixtures("temp_repo", "mock_bin")
@pytest.mark.asyncio
async def test_happy_path(mock_instructions):
    """
    Test a full successful workflow run.
    """
    instructions = {
        "gemini": [
            # Coder: implements feature
            {
                "stdout": "I implemented the feature and tests.",
                "write_files": {
                    "src/feature.py": "def hello(): return 'world'",
                    "test/test_feature.py": "from src.feature import hello\ndef test_hello(): assert hello() == 'world'",
                },
                "shell": "git add . && git commit -m 'feat: implement hello'",
            },
            # Architect: approves
            {
                "stdout": "Structure looks good. VERDICT: OK",
            },
            # Reviewer: approves
            {
                "stdout": "LGTM. VERDICT: APPROVED",
            },
            # Journaler: distills lesson
            {
                "stdout": "Always use TDD.",
            },
        ],
        "pytest": [
            # WorkflowManager baseline check
            {"stdout": "3 passed"},
            # Tester node run
            {"stdout": "3 passed"},
        ],
        "ruff": [
            # Tester node run
            {"stdout": ""},
        ],
        "gh": [
            # PR Creator
            {"stdout": "https://github.com/gfxblit/copium-loop/pull/123"},
        ],
    }
    mock_instructions.write_text(json.dumps(instructions))

    wm = WorkflowManager()
    result = await wm.run("Implement a hello world feature")

    assert "pr_url" in result
    assert result["pr_url"] == "https://github.com/gfxblit/copium-loop/pull/123"
    assert result["code_status"] == "coded"
    assert result["review_status"] == "pr_created"
    assert os.path.exists("src/feature.py")
    assert os.path.exists("test/test_feature.py")


@pytest.mark.usefixtures("temp_repo", "mock_bin")
@pytest.mark.asyncio
async def test_retry_loop(mock_instructions):
    """
    Test workflow retrying when tests fail.
    """
    instructions = {
        "gemini": [
            # First Coder run: writes buggy code
            {
                "stdout": "I implemented the feature with a bug.",
                "write_files": {
                    "src/feature.py": "def hello(): return 'wrong'",
                    "test/test_feature.py": "from src.feature import hello\ndef test_hello(): assert hello() == 'world'",
                },
                "shell": "git add . && git commit -m 'feat: initial bug'",
            },
            # Second Coder run (after test failure): fixes bug
            {
                "stdout": "I fixed the bug.",
                "write_files": {"src/feature.py": "def hello(): return 'world'"},
                "shell": "git add . && git commit -m 'fix: bug'",
            },
            # Architect: approves
            {
                "stdout": "Structure looks good. VERDICT: OK",
            },
            # Reviewer: approves
            {
                "stdout": "LGTM. VERDICT: APPROVED",
            },
            # Journaler: distills lesson
            {
                "stdout": "Fix bugs promptly.",
            },
        ],
        "pytest": [
            # WorkflowManager baseline check
            {"stdout": "0 passed"},
            # First Tester run: fails
            {"stdout": "1 failed", "exit_code": 1},
            # Second Tester run: passes
            {"stdout": "1 passed"},
        ],
        "ruff": [
            # First Tester run
            {"stdout": ""},
            # Second Tester run
            {"stdout": ""},
        ],
        "gh": [
            {"stdout": "https://github.com/gfxblit/copium-loop/pull/124"},
        ],
    }
    mock_instructions.write_text(json.dumps(instructions))

    wm = WorkflowManager()
    result = await wm.run("Fix the hello feature")

    assert result["retry_count"] == 1
    assert result["pr_url"] == "https://github.com/gfxblit/copium-loop/pull/124"


@pytest.mark.usefixtures("temp_repo", "mock_bin")
@pytest.mark.asyncio
async def test_max_retries_exceeded(mock_instructions, monkeypatch):
    """
    Test workflow stopping after MAX_RETRIES.
    """
    import copium_loop.constants

    monkeypatch.setattr(copium_loop.constants, "MAX_RETRIES", 2)

    instructions = {
        "gemini": [
            {"stdout": "Attempt 1", "write_files": {"f.py": ""}},
            {"stdout": "Attempt 2", "write_files": {"f.py": ""}},
            {"stdout": "Attempt 3", "write_files": {"f.py": ""}},
            {"stdout": "Max retries lesson."},
        ],
        "pytest": [
            {"stdout": "Baseline"},
            {"stdout": "Fail 1", "exit_code": 1},
            {"stdout": "Fail 2", "exit_code": 1},
            {"stdout": "Fail 3", "exit_code": 1},
        ],
        "ruff": [
            {"stdout": ""},
            {"stdout": ""},
            {"stdout": ""},
        ],
    }
    mock_instructions.write_text(json.dumps(instructions))

    wm = WorkflowManager()
    result = await wm.run("Persistent failure")

    from copium_loop.constants import MAX_RETRIES

    assert MAX_RETRIES == 2
    assert result["retry_count"] == MAX_RETRIES
    # When tester fails and max retries reached, it returns state with error
    assert "FAIL (Unit)" in result["test_output"]


@pytest.mark.usefixtures("temp_repo", "mock_bin")
@pytest.mark.asyncio
async def test_pr_creation_failure(mock_instructions):
    """
    Test workflow handling PR creation failure.
    """
    instructions = {
        "gemini": [
            {
                "stdout": "Implemented",
                "write_files": {"f.py": ""},
                "shell": "git add . && git commit -m 'feat'",
            },
            {
                "stdout": "Architect: OK. VERDICT: OK",
            },
            {
                "stdout": "VERDICT: APPROVED",
            },
        ],
        "pytest": [{"stdout": "Baseline"}, {"stdout": "Pass"}],
        "ruff": [{"stdout": ""}],
        "gh": [
            # PR Creator: gh pr create fails
            {"stdout": "Error: GraphQL error", "exit_code": 1},
        ],
    }
    mock_instructions.write_text(json.dumps(instructions))

    wm = WorkflowManager()
    result = await wm.run("Feature with PR fail")

    # It returns to coder, which fails because no more instructions
    assert result["review_status"] == "pr_failed"
    assert "GraphQL error" in str(result["messages"])


@pytest.mark.usefixtures("temp_repo", "mock_bin")
@pytest.mark.asyncio
async def test_architect_refactor_loop(mock_instructions):
    """
    Test workflow looping from architect back to coder on REFACTOR verdict.
    """
    instructions = {
        "gemini": [
            # 1. Coder: implements feature
            {
                "stdout": "I implemented the feature.",
                "write_files": {
                    "src/feature.py": "def hello():\n    print('hello')\n    return 'world'",
                },
                "shell": "git add . && git commit -m 'feat: initial implementation'",
            },
            # 2. Architect: requests refactor
            {
                "stdout": "Please remove the print statement. VERDICT: REFACTOR",
            },
            # 3. Coder: refactors
            {
                "stdout": "I removed the print statement.",
                "write_files": {
                    "src/feature.py": "def hello():\n    return 'world'",
                },
                "shell": "git add . && git commit -m 'refactor: remove print'",
            },
            # 4. Architect: approves
            {
                "stdout": "Looks better. VERDICT: OK",
            },
            # 5. Reviewer: approves
            {
                "stdout": "LGTM. VERDICT: APPROVED",
            },
            # 6. Journaler: distills lesson
            {
                "stdout": "Avoid unnecessary prints.",
            },
        ],
        "pytest": [
            # Baseline check
            {"stdout": "0 passed"},
            # First Tester run
            {"stdout": "0 passed"},
            # Second Tester run
            {"stdout": "0 passed"},
        ],
        "ruff": [
            # First Tester run
            {"stdout": ""},
            # Second Tester run
            {"stdout": ""},
        ],
        "gh": [
            {"stdout": "https://github.com/gfxblit/copium-loop/pull/125"},
        ],
    }
    mock_instructions.write_text(json.dumps(instructions))

    wm = WorkflowManager()
    result = await wm.run("Implement hello without prints")

    assert result["architect_status"] == "ok"
    assert result["pr_url"] == "https://github.com/gfxblit/copium-loop/pull/125"
    assert result["retry_count"] == 1  # One retry due to architect refactor
