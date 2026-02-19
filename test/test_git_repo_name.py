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
            # Mock git remote -v output
            output = f"origin\t{url} (fetch)\norigin\t{url} (push)\n"
            mock_run.return_value = {"exit_code": 0, "output": output}

            repo = await get_repo_name()
            assert repo == expected
            mock_run.assert_called_with("git", ["remote", "-v"], node=None, capture_stderr=False)


@pytest.mark.asyncio
async def test_get_repo_name_no_remote():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        # git remote -v failed or empty
        mock_run.return_value = {"exit_code": 0, "output": ""}
        with pytest.raises(ValueError, match="Could not determine git remote URL"):
            await get_repo_name()


@pytest.mark.asyncio
async def test_get_repo_name_unsupported_url():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        url = "https://example.com/not-a-repo"
        output = f"origin\t{url} (fetch)\norigin\t{url} (push)\n"
        mock_run.return_value = {"exit_code": 0, "output": output}

        with pytest.raises(
            ValueError, match="Could not parse repo name from remote URL"
        ):
            await get_repo_name()

@pytest.mark.asyncio
async def test_get_repo_name_multiple_remotes():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        # origin should be preferred even if it's not first in the list (though usually it is)
        # Here we put upstream first to test logic
        output = (
            "upstream\thttps://github.com/upstream/repo.git (fetch)\n"
            "upstream\thttps://github.com/upstream/repo.git (push)\n"
            "origin\thttps://github.com/myuser/myfork.git (fetch)\n"
            "origin\thttps://github.com/myuser/myfork.git (push)\n"
        )
        mock_run.return_value = {"exit_code": 0, "output": output}

        repo = await get_repo_name()
        # Should pick origin
        assert repo == "myuser/myfork"

@pytest.mark.asyncio
async def test_get_repo_name_fallback_no_origin():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        output = (
            "upstream\thttps://github.com/upstream/repo.git (fetch)\n"
            "upstream\thttps://github.com/upstream/repo.git (push)\n"
        )
        mock_run.return_value = {"exit_code": 0, "output": output}

        repo = await get_repo_name()
        # Should pick the available remote
        assert repo == "upstream/repo"
