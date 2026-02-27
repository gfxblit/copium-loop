from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import git


@pytest.fixture
def clear_git_cache():
    """Clear the git cache before and after tests."""
    git._BRANCH_CACHE.clear()
    yield
    git._BRANCH_CACHE.clear()


@pytest.mark.asyncio
async def test_get_repo_name_caching(clear_git_cache):  # noqa: ARG001
    """Test that get_repo_name caches the result."""

    # Mock run_command to return a valid remote URL
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        url = "https://github.com/owner/repo.git"
        output = f"origin\t{url} (fetch)\norigin\t{url} (push)\n"
        mock_run.return_value = {"exit_code": 0, "output": output}

        # First call: should trigger run_command
        repo1 = await git.get_repo_name()
        assert repo1 == "owner/repo"
        assert mock_run.call_count == 1

        # Second call: should use cache
        repo2 = await git.get_repo_name()
        assert repo2 == "owner/repo"
        assert mock_run.call_count == 1  # Still 1


@pytest.mark.asyncio
async def test_get_repo_name_cache_invalidation_on_dir_change(clear_git_cache):  # noqa: ARG001
    """Test that cache is keyed by directory."""

    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        url = "https://github.com/owner/repo.git"
        output = f"origin\t{url} (fetch)\norigin\t{url} (push)\n"
        mock_run.return_value = {"exit_code": 0, "output": output}

        with patch("os.getcwd") as mock_getcwd:
            # First directory
            mock_getcwd.return_value = "/dir1"
            await git.get_repo_name()
            assert mock_run.call_count == 1

            # Same directory, should cache
            await git.get_repo_name()
            assert mock_run.call_count == 1

            # Change directory
            mock_getcwd.return_value = "/dir2"
            await git.get_repo_name()
            assert mock_run.call_count == 2
