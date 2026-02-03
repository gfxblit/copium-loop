import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import git


@pytest.mark.asyncio
async def test_get_current_branch():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"output": "main\n", "exit_code": 0}
        branch = await git.get_current_branch()
        assert branch == "main"
        mock_run.assert_called_with("git", ["branch", "--show-current"], node=None)


@pytest.mark.asyncio
async def test_get_diff():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"output": "diff content", "exit_code": 0}
        diff = await git.get_diff("HEAD~1", "HEAD")
        assert diff == "diff content"
        mock_run.assert_called_with("git", ["diff", "HEAD~1", "HEAD"], node=None)


@pytest.mark.asyncio
async def test_is_dirty():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"output": "M file.py\n", "exit_code": 0}
        assert await git.is_dirty() is True
        mock_run.assert_called_with("git", ["status", "--porcelain"], node=None)

        mock_run.return_value = {"output": "", "exit_code": 0}
        assert await git.is_dirty() is False


@pytest.mark.asyncio
async def test_get_head():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"output": "abc123\n", "exit_code": 0}
        head = await git.get_head()
        assert head == "abc123"
        mock_run.assert_called_with("git", ["rev-parse", "HEAD"], node=None)


@pytest.mark.asyncio
async def test_fetch():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}
        await git.fetch()
        mock_run.assert_called_with("git", ["fetch", "origin"], node=None)


@pytest.mark.asyncio
async def test_rebase():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}
        await git.rebase("origin/main")
        mock_run.assert_called_with("git", ["rebase", "origin/main"], node=None)


@pytest.mark.asyncio
async def test_rebase_abort():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}
        await git.rebase_abort()
        mock_run.assert_called_with("git", ["rebase", "--abort"], node=None)


@pytest.mark.asyncio
async def test_push():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}

        # Test default push
        await git.push()
        mock_run.assert_called_with("git", ["push", "origin"], node=None)

        # Test force push
        await git.push(force=True)
        mock_run.assert_called_with("git", ["push", "--force", "origin"], node=None)

        # Test push specific branch
        await git.push(branch="my-branch")
        mock_run.assert_called_with("git", ["push", "-u", "origin", "my-branch"], node=None)


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_git_repo")
async def test_diff_uncommitted():
    """Test that get_diff captures uncommitted changes when head is None."""
    # Create a file and commit it
    with open("test.txt", "w") as f:
        f.write("initial content")
    subprocess.run(["git", "add", "test.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "initial commit", "-q"], check=True)

    # Get base commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    base_commit = result.stdout.strip()

    # Modify the file (uncommitted change)
    with open("test.txt", "w") as f:
        f.write("modified content")

    # Test get_diff with head=None (should capture uncommitted changes)
    diff = await git.get_diff(base_commit, head=None)
    assert "modified content" in diff
    assert "initial content" in diff


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_git_repo")
async def test_diff_committed():
    """Test that get_diff captures changes between two commits."""
    # Create a file and commit it
    with open("test.txt", "w") as f:
        f.write("initial content")
    subprocess.run(["git", "add", "test.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "initial commit", "-q"], check=True)

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    base_commit = result.stdout.strip()

    # Modify and commit
    with open("test.txt", "w") as f:
        f.write("modified content")
    subprocess.run(["git", "add", "test.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "second commit", "-q"], check=True)

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    head_commit = result.stdout.strip()

    # Test get_diff with explicit head
    diff = await git.get_diff(base_commit, head=head_commit)

    assert "modified content" in diff
    assert "initial content" in diff
