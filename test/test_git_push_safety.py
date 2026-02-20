from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import git


@pytest.mark.asyncio
async def test_push_force_with_lease():
    """Test that git.push uses --force-with-lease instead of --force."""
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}
        with patch(
            "copium_loop.git.get_current_branch", new_callable=AsyncMock
        ) as mock_branch:
            mock_branch.return_value = "feature-branch"

            # Test force push
            await git.push(force=True)
            # It should use --force-with-lease
            mock_run.assert_called_with(
                "git", ["push", "--force-with-lease", "origin"], node=None
            )


@pytest.mark.asyncio
async def test_push_protected_branch_fails():
    """Test that git.push fails when trying to force push to a protected branch."""
    protected_branches = ["main", "master", "develop", "release"]
    for branch in protected_branches:
        with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"exit_code": 0}
            with patch(
                "copium_loop.git.get_current_branch", new_callable=AsyncMock
            ) as mock_branch:
                mock_branch.return_value = branch

                # Should raise ValueError or similar when trying to force push to protected branch
                with pytest.raises(
                    ValueError, match=f"Cannot force push to protected branch: {branch}"
                ):
                    await git.push(force=True)

                # Ensure git push was NOT called
                mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_push_non_protected_branch_succeeds():
    """Test that git.push succeeds when force pushing to a non-protected branch."""
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}
        with patch(
            "copium_loop.git.get_current_branch", new_callable=AsyncMock
        ) as mock_branch:
            mock_branch.return_value = "feature/new-ui"

            await git.push(force=True)
            mock_run.assert_called_with(
                "git", ["push", "--force-with-lease", "origin"], node=None
            )
