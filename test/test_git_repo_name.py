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
            mock_run.side_effect = [
                {"exit_code": 0, "output": "origin\n"},
                {"exit_code": 0, "output": url + "\n"},
            ]
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
        mock_run.side_effect = [
            {"exit_code": 0, "output": "origin\n"},
            {"exit_code": 0, "output": "https://example.com/not-a-repo\n"},
        ]
        with pytest.raises(
            ValueError, match="Could not parse repo name from remote URL"
        ):
            await get_repo_name()
