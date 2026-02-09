import sys
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import pr_creator

# Get the module object explicitly to avoid shadowing issues
pr_creator_module = sys.modules["copium_loop.nodes.pr_creator"]


class TestPrCreatorNode:
    """Tests for the PR creator node."""

    @pytest.mark.asyncio
    @patch.object(pr_creator_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "get_current_branch", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "is_dirty", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "add", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "commit", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "push", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "run_command", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "os")
    async def test_pr_creator_creates_pr(
        self,
        mock_os,
        mock_run,
        mock_push,
        mock_commit,
        mock_add,
        mock_is_dirty,
        mock_branch,
        mock_is_git,
    ):
        """Test that PR creator creates a PR successfully."""
        mock_is_git.return_value = True
        mock_os.path.exists.return_value = True

        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_push.return_value = {"exit_code": 0}
        mock_run.return_value = {
            "output": "https://github.com/org/repo/pull/1\n",
            "exit_code": 0,
        }

        state = {"retry_count": 0}
        result = await pr_creator(state)

        assert result["review_status"] == "pr_created"
        assert "PR Created" in result["messages"][0].content
        mock_push.assert_called_with(
            force=True, branch="feature-branch", node="pr_creator"
        )
        mock_add.assert_not_called()
        mock_commit.assert_not_called()

    @pytest.mark.asyncio
    @patch.object(pr_creator_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "get_current_branch", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "is_dirty", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "add", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "commit", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "push", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "run_command", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "os")
    async def test_pr_creator_commits_dirty_files(
        self,
        mock_os,
        mock_run,
        mock_push,
        mock_commit,
        mock_add,
        mock_is_dirty,
        mock_branch,
        mock_is_git,
    ):
        """Test that PR creator commits dirty files (from journaler)."""
        mock_is_git.return_value = True
        mock_os.path.exists.return_value = True

        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = True
        mock_add.return_value = {"exit_code": 0}
        mock_commit.return_value = {"exit_code": 0}
        mock_push.return_value = {"exit_code": 0}
        mock_run.return_value = {
            "output": "https://github.com/org/repo/pull/1\n",
            "exit_code": 0,
        }

        state = {"retry_count": 0}
        result = await pr_creator(state)

        assert result["review_status"] == "pr_created"
        mock_add.assert_called_once_with(".", node="pr_creator")
        mock_commit.assert_called_once_with(
            "docs: update GEMINI.md and session memory", node="pr_creator"
        )
        mock_push.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(pr_creator_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "get_current_branch", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "is_dirty", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "push", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "run_command", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "os")
    async def test_pr_creator_handles_existing_pr(
        self,
        mock_os,
        mock_run,
        mock_push,
        mock_is_dirty,
        mock_branch,
        mock_is_git,
    ):
        """Test that PR creator handles existing PR."""
        mock_is_git.return_value = True
        mock_os.path.exists.return_value = True

        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_push.return_value = {"exit_code": 0}
        mock_run.return_value = {
            "output": "already exists: https://github.com/org/repo/pull/1\n",
            "exit_code": 1,
        }

        state = {"retry_count": 0}
        result = await pr_creator(state)

        assert result["review_status"] == "pr_created"
        assert "already exists" in result["messages"][0].content

    @pytest.mark.asyncio
    @patch.object(pr_creator_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "get_current_branch", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "os")
    async def test_pr_creator_skips_on_main_branch(self, mock_os, mock_branch, mock_is_git):
        """Test that PR creator skips on main branch."""
        mock_is_git.return_value = True
        mock_os.path.exists.return_value = True

        mock_branch.return_value = "main"

        state = {"retry_count": 0}
        result = await pr_creator(state)

        assert result["review_status"] == "pr_skipped"

    @pytest.mark.asyncio
    @patch.object(pr_creator_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "os")
    async def test_pr_creator_no_git(self, mock_os, mock_is_git):
        """Test that PR creator skips if not a git repository."""
        mock_is_git.return_value = False
        mock_os.path.exists.return_value = False
        result = await pr_creator({"retry_count": 0})
        assert result["review_status"] == "pr_skipped"


    @pytest.mark.asyncio
    @patch.object(pr_creator_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "get_current_branch", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "is_dirty", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "push", new_callable=AsyncMock)
    @patch.object(pr_creator_module, "os")
    async def test_pr_creator_push_failure(
        self,
        mock_os,
        mock_push,
        mock_is_dirty,
        mock_branch,
        mock_is_git,
    ):
        """Test that PR creator handles push failure."""
        mock_is_git.return_value = True
        mock_os.path.exists.return_value = True

        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_push.return_value = {"exit_code": 1, "output": "push failed"}

        result = await pr_creator({"retry_count": 0})
        assert result["review_status"] == "pr_failed"
        assert "Git push failed" in result["messages"][0].content
