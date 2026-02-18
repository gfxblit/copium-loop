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
            mock_run.assert_called_once()
            args, _ = mock_run.call_args
            assert args[1] == ["remote", "-v"]


@pytest.mark.asyncio
async def test_get_repo_name_prioritize_origin():
    # origin is listed AFTER upstream, but should be prioritized
    output = """
upstream\tgit@github.com:upstream/repo.git (fetch)
upstream\tgit@github.com:upstream/repo.git (push)
origin\tgit@github.com:origin/repo.git (fetch)
origin\tgit@github.com:origin/repo.git (push)
    """.strip()

    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0, "output": output}
        repo = await get_repo_name()
        assert repo == "origin/repo"


@pytest.mark.asyncio
async def test_get_repo_name_fallback():
    # No origin, should pick upstream
    output = """
upstream\tgit@github.com:upstream/repo.git (fetch)
upstream\tgit@github.com:upstream/repo.git (push)
    """.strip()

    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0, "output": output}
        repo = await get_repo_name()
        assert repo == "upstream/repo"


@pytest.mark.asyncio
async def test_get_repo_name_no_remote():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0, "output": ""}
        with pytest.raises(ValueError, match="Could not determine git remote URL"):
            await get_repo_name()


@pytest.mark.asyncio
async def test_get_repo_name_unsupported_url():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        output = "origin\thttps://example.com/not-a-repo (fetch)\n"
        mock_run.return_value = {"exit_code": 0, "output": output}

        with pytest.raises(
            ValueError, match="Could not parse repo name from remote URL"
        ):
            await get_repo_name()
