from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import pr_creator


class TestPrCreatorNode:
    """Tests for the PR creator node."""

    @pytest.mark.asyncio
    async def test_pr_creator_creates_pr(self):
        """Test that PR creator creates a PR successfully."""
        with patch(
            "copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = [
                {"output": "feature-branch\n", "exit_code": 0},  # branch
                {"output": "", "exit_code": 0},  # status
                {"output": "", "exit_code": 0},  # fetch
                {"output": "", "exit_code": 0},  # rebase
                {"output": "", "exit_code": 0},  # push
                {
                    "output": "https://github.com/org/repo/pull/1\n",
                    "exit_code": 0,
                },  # pr
            ]

            state = {"retry_count": 0}
            result = await pr_creator(state)

            assert result["review_status"] == "pr_created"
            assert "PR Created" in result["messages"][0].content

            # Check that git push was called with --force
            push_call = [
                call for call in mock_run.call_args_list if call[0][0] == "git" and "push" in call[0][1]
            ][0]
            assert "--force" in push_call[0][1]

    @pytest.mark.asyncio
    async def test_pr_creator_handles_existing_pr(self):
        """Test that PR creator handles existing PR."""
        with patch(
            "copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = [
                {"output": "feature-branch\n", "exit_code": 0},
                {"output": "", "exit_code": 0},
                {"output": "", "exit_code": 0},  # fetch
                {"output": "", "exit_code": 0},  # rebase
                {"output": "", "exit_code": 0},
                {
                    "output": "already exists: https://github.com/org/repo/pull/1\n",
                    "exit_code": 1,
                },
            ]

            state = {"retry_count": 0}
            result = await pr_creator(state)

            assert result["review_status"] == "pr_created"
            assert "already exists" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_pr_creator_needs_commit(self):
        """Test that PR creator detects uncommitted changes."""
        with patch(
            "copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = [
                {"output": "feature-branch\n", "exit_code": 0},
                {"output": "M file.js\n", "exit_code": 0},
            ]
            state = {"retry_count": 0}
            result = await pr_creator(state)

            assert result["review_status"] == "needs_commit"

    @pytest.mark.asyncio
    async def test_pr_creator_skips_on_main_branch(self):
        """Test that PR creator skips on main branch."""
        with patch(
            "copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.return_value = {"output": "main\n", "exit_code": 0}

            state = {"retry_count": 0}
            result = await pr_creator(state)

            assert result["review_status"] == "pr_skipped"

    @pytest.mark.asyncio
    async def test_pr_creator_references_issue(self):
        """Test that PR creator references and closes the issue."""
        with patch(
            "copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = [
                {"output": "feature-branch\n", "exit_code": 0},  # branch
                {"output": "", "exit_code": 0},  # status
                {"output": "", "exit_code": 0},  # fetch
                {"output": "", "exit_code": 0},  # rebase
                {"output": "", "exit_code": 0},  # push
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

            # Check that git push was called with --force
            push_call = [
                call for call in mock_run.call_args_list if call[0][0] == "git" and "push" in call[0][1]
            ][0]
            assert "--force" in push_call[0][1]

            # Check that pr edit was called with the "Closes" message
            edit_call = mock_run.call_args_list[-1]
            assert edit_call[0][0] == "gh"
            args = edit_call[0][1]
            assert "pr" in args
            assert "edit" in args
            assert "--body" in args
            # The body is the argument immediately following --body
            body_arg_index = args.index("--body") + 1
            assert "Closes https://github.com/org/repo/issues/123" in args[body_arg_index]

    @pytest.mark.asyncio
    async def test_pr_creator_fails_on_rebase(self):
        """Test that PR creator fails gracefully when rebase fails."""
        with patch(
            "copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = [
                {"output": "feature-branch\n", "exit_code": 0},  # branch
                {"output": "", "exit_code": 0},  # status
                {"output": "", "exit_code": 0},  # fetch
                {"output": "CONFLICT\n", "exit_code": 1},  # rebase fails
                {"output": "", "exit_code": 0},  # rebase abort
            ]

            state = {"retry_count": 0}
            result = await pr_creator(state)

            assert result["review_status"] == "pr_failed"
            assert "rebase on origin/main failed" in result["messages"][0].content
            assert result["retry_count"] == 1
