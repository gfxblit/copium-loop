from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import pr_creator


class TestPrCreatorNode:
    """Tests for the PR creator node."""

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.pr_creator.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.push", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock)
    @patch("os.path.exists")
    async def test_pr_creator_creates_pr(self, mock_exists, mock_run, mock_push, mock_rebase, mock_fetch, mock_is_dirty, mock_branch):
        """Test that PR creator creates a PR successfully."""
        mock_exists.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_fetch.return_value = {"exit_code": 0}
        mock_rebase.return_value = {"exit_code": 0}
        mock_push.return_value = {"exit_code": 0}
        mock_run.return_value = {
            "output": "https://github.com/org/repo/pull/1\n",
            "exit_code": 0,
        }

        state = {"retry_count": 0}
        result = await pr_creator(state)

        assert result["review_status"] == "pr_created"
        assert "PR Created" in result["messages"][0].content
        mock_push.assert_called_with(force=True, branch="feature-branch")

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.pr_creator.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.push", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock)
    @patch("os.path.exists")
    async def test_pr_creator_handles_existing_pr(self, mock_exists, mock_run, mock_push, mock_rebase, mock_fetch, mock_is_dirty, mock_branch):
        """Test that PR creator handles existing PR."""
        mock_exists.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_fetch.return_value = {"exit_code": 0}
        mock_rebase.return_value = {"exit_code": 0}
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
    @patch("copium_loop.nodes.pr_creator.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.is_dirty", new_callable=AsyncMock)
    @patch("os.path.exists")
    async def test_pr_creator_needs_commit(self, mock_exists, mock_is_dirty, mock_branch):
        """Test that PR creator detects uncommitted changes."""
        mock_exists.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = True

        state = {"retry_count": 0}
        result = await pr_creator(state)

        assert result["review_status"] == "needs_commit"

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.pr_creator.get_current_branch", new_callable=AsyncMock)
    @patch("os.path.exists")
    async def test_pr_creator_skips_on_main_branch(self, mock_exists, mock_branch):
        """Test that PR creator skips on main branch."""
        mock_exists.return_value = True
        mock_branch.return_value = "main"

        state = {"retry_count": 0}
        result = await pr_creator(state)

        assert result["review_status"] == "pr_skipped"

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.pr_creator.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.push", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock)
    @patch("os.path.exists")
    async def test_pr_creator_references_issue(self, mock_exists, mock_run, mock_push, mock_rebase, mock_fetch, mock_is_dirty, mock_branch):
        """Test that PR creator references and closes the issue."""
        mock_exists.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_fetch.return_value = {"exit_code": 0}
        mock_rebase.return_value = {"exit_code": 0}
        mock_push.return_value = {"exit_code": 0}
        mock_run.side_effect = [
            {
                "output": "https://github.com/org/repo/pull/1\n",
                "exit_code": 0,
            },  # pr create
            {
                "output": "Initial PR body\n",
                "exit_code": 0,
            },  # pr view
            {"output": "", "exit_code": 0},  # pr edit
        ]

        state = {
            "retry_count": 0,
            "issue_url": "https://github.com/org/repo/issues/123",
        }
        result = await pr_creator(state)

        assert result["review_status"] == "pr_created"
        assert result["pr_url"] == "https://github.com/org/repo/pull/1"

        # Check that pr edit was called with the "Closes" message
        edit_call = mock_run.call_args_list[-1]
        assert edit_call[0][0] == "gh"
        args = edit_call[0][1]
        assert "pr" in args
        assert "edit" in args
        assert "--body" in args
        body_arg_index = args.index("--body") + 1
        assert (
            "Closes https://github.com/org/repo/issues/123" in args[body_arg_index]
        )

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.pr_creator.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.rebase_abort", new_callable=AsyncMock)
    @patch("os.path.exists")
    async def test_pr_creator_fails_on_rebase(self, mock_exists, mock_abort, mock_rebase, mock_fetch, mock_is_dirty, mock_branch):
        """Test that PR creator fails gracefully when rebase fails."""
        mock_exists.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_fetch.return_value = {"exit_code": 0}
        mock_rebase.return_value = {"output": "CONFLICT\n", "exit_code": 1}
        mock_abort.return_value = {"exit_code": 0}

        state = {"retry_count": 0}
        result = await pr_creator(state)

        assert result["review_status"] == "pr_failed"
        assert "rebase on origin/main failed" in result["messages"][0].content
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_pr_creator_no_git(self, mock_exists):
        """Test that PR creator skips if not a git repository."""
        mock_exists.return_value = False
        result = await pr_creator({"retry_count": 0})
        assert result["review_status"] == "pr_skipped"

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.pr_creator.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.push", new_callable=AsyncMock)
    @patch("os.path.exists")
    async def test_pr_creator_push_failure(self, mock_exists, mock_push, mock_rebase, mock_fetch, mock_is_dirty, mock_branch):
        """Test that PR creator handles push failure."""
        mock_exists.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_fetch.return_value = {"exit_code": 0}
        mock_rebase.return_value = {"exit_code": 0}
        mock_push.return_value = {"exit_code": 1, "output": "push failed"}

        result = await pr_creator({"retry_count": 0})
        assert result["review_status"] == "pr_failed"
        assert "Git push failed" in result["messages"][0].content

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.pr_creator.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.push", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock)
    @patch("os.path.exists")
    async def test_pr_creator_issue_linking_failure(self, mock_exists, mock_run, mock_push, mock_rebase, mock_fetch, mock_is_dirty, mock_branch):
        """Test that PR creator continues if issue linking fails."""
        mock_exists.return_value = True
        mock_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_fetch.return_value = {"exit_code": 0}
        mock_rebase.return_value = {"exit_code": 0}
        mock_push.return_value = {"exit_code": 0}

        mock_run.side_effect = [
            {"output": "https://github.com/org/repo/pull/1", "exit_code": 0}, # pr create
            Exception("view failed") # pr view fails
        ]

        result = await pr_creator({"retry_count": 0, "issue_url": "http://issue"})
        assert result["review_status"] == "pr_created"
        assert result["pr_url"] == "https://github.com/org/repo/pull/1"

    @pytest.mark.asyncio
    @patch("os.path.exists")
    async def test_pr_creator_general_exception(self, mock_exists):
        """Test that PR creator handles general exceptions."""
        mock_exists.side_effect = Exception("unexpected error")
        result = await pr_creator({"retry_count": 0})
        assert result["review_status"] == "pr_failed"
        assert "unexpected error" in result["messages"][0].content
