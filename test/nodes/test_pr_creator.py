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

    @pytest.mark.asyncio
    async def test_pr_creator_handles_existing_pr(self):
        """Test that PR creator handles existing PR."""
        with patch(
            "copium_loop.nodes.pr_creator.run_command", new_callable=AsyncMock
        ) as mock_run:
            mock_run.side_effect = [
                {"output": "feature-branch\n", "exit_code": 0},
                {"output": "", "exit_code": 0},
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
            with patch("copium_loop.nodes.pr_creator.notify", new_callable=AsyncMock):
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
