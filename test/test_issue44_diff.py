import os
import shutil
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import git
from copium_loop.nodes.architect import architect


@pytest.fixture
def temp_git_repo():
    # Create a temp dir
    temp_dir = tempfile.mkdtemp()
    original_cwd = os.getcwd()
    os.chdir(temp_dir)

    # Initialize git repo
    os.system("git init")
    os.system("git config user.email 'you@example.com'")
    os.system("git config user.name 'Your Name'")

    yield temp_dir

    # Cleanup
    os.chdir(original_cwd)
    shutil.rmtree(temp_dir)


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_git_repo")
async def test_diff_uncommitted():
    # Create a file and commit it
    with open("test.txt", "w") as f:
        f.write("initial content")
    os.system("git add test.txt")
    os.system("git commit -m 'initial commit'")

    # Get base commit hash
    base_commit = os.popen("git rev-parse HEAD").read().strip()

    # Modify the file (uncommitted change)
    with open("test.txt", "w") as f:
        f.write("modified content")

    # Test get_diff with head=None (should capture uncommitted changes)
    # This might raise TypeError before implementation, which counts as failing.
    try:
        diff = await git.get_diff(base_commit, head=None)
        assert "modified content" in diff
        assert "initial content" in diff
    except TypeError:
        pytest.fail("get_diff raised TypeError with head=None")
    except Exception as e:
        pytest.fail(f"get_diff failed with error: {e}")


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_git_repo")
async def test_diff_committed():
    # Create a file and commit it
    with open("test.txt", "w") as f:
        f.write("initial content")
    os.system("git add test.txt")
    os.system("git commit -m 'initial commit'")

    base_commit = os.popen("git rev-parse HEAD").read().strip()

    # Modify and commit
    with open("test.txt", "w") as f:
        f.write("modified content")
    os.system("git add test.txt")
    os.system("git commit -m 'second commit'")

    head_commit = os.popen("git rev-parse HEAD").read().strip()

    # Test get_diff with explicit head
    diff = await git.get_diff(base_commit, head=head_commit)

    assert "modified content" in diff
    assert "initial content" in diff


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_git_repo")
async def test_architect_integration():
    # Setup repo with uncommitted changes
    with open("test.txt", "w") as f:
        f.write("initial content")
    os.system("git add test.txt")
    os.system("git commit -m 'initial commit'")

    initial_commit = os.popen("git rev-parse HEAD").read().strip()

    with open("test.txt", "w") as f:
        f.write("modified content")

    # Mock state
    state = {
        "initial_commit_hash": initial_commit,
        "retry_count": 0,
        "verbose": False
    }

    # Mock invoke_gemini
    # We patch it where it is imported in architect.py
    with patch("copium_loop.nodes.architect.invoke_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = "VERDICT: OK"

        # Run architect node
        result = await architect(state)

        # Verify call args
        args, kwargs = mock_gemini.call_args
        system_prompt = args[0]

        # This assertion should fail before the fix because get_diff defaults to HEAD
        assert "modified content" in system_prompt
        assert result["architect_status"] == "ok"
