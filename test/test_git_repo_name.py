from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.git import get_repo_name


@pytest.mark.asyncio
async def test_get_repo_name_parsing():
    urls = [
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo", "owner/repo"),
        ("git@github.com:owner/repo", "owner/repo"),
        ("https://github.com/owner/repo/", "owner/repo"),
        ("https://github.com/user/my.project.git", "user/my.project"),
        ("git@github.com:user/my.project.git", "user/my.project"),
    ]

    for url, expected in urls:
        with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
            # Simulate 'git remote -v' output
            mock_run.return_value = {
                "exit_code": 0,
                "output": f"origin\t{url} (fetch)\norigin\t{url} (push)\n",
            }
            repo = await get_repo_name()
            assert repo == expected


@pytest.mark.asyncio
async def test_get_repo_name_no_remote():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0, "output": ""}
        with pytest.raises(ValueError, match="Could not determine git remote URL"):
            await get_repo_name()


@pytest.mark.asyncio
async def test_get_repo_name_unsupported_url():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        url = "https://example.com/not-a-repo"
        mock_run.return_value = {
            "exit_code": 0,
            "output": f"origin\t{url} (fetch)\norigin\t{url} (push)\n",
        }
        with pytest.raises(
            ValueError, match=f"Could not parse repo name from remote URL: {url}"
        ):
            await get_repo_name()


@pytest.mark.asyncio
async def test_get_repo_name_priority():
    # Test that 'origin' is prioritized over other remotes
    other_url = "https://github.com/other/repo.git"
    origin_url = "https://github.com/origin/repo.git"

    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {
            "exit_code": 0,
            "output": f"upstream\t{other_url} (fetch)\norigin\t{origin_url} (fetch)\norigin\t{origin_url} (push)\nupstream\t{other_url} (push)\n",
        }
        repo = await get_repo_name()
        assert repo == "origin/repo"


@pytest.mark.asyncio
async def test_get_repo_name_fallback():
    # Test fallback to first available remote if origin is missing
    other_url = "https://github.com/other/repo.git"

    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {
            "exit_code": 0,
            "output": f"upstream\t{other_url} (fetch)\nupstream\t{other_url} (push)\n",
        }
        repo = await get_repo_name()
        assert repo == "other/repo"
