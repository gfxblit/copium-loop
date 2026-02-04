from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes.pr_pre_checker import pr_pre_checker
from copium_loop.state import AgentState


@pytest.mark.asyncio
class TestPRPreChecker:
    @patch("copium_loop.nodes.pr_pre_checker.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.os.path.exists")
    async def test_pr_pre_checker_success(
        self, mock_exists, mock_rebase, mock_fetch, mock_is_dirty, mock_get_branch
    ):
        mock_exists.return_value = True
        mock_get_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_rebase.return_value = {"exit_code": 0, "output": "Successfully rebased"}

        state: AgentState = {"retry_count": 0}
        result = await pr_pre_checker(state)

        assert result["review_status"] == "pre_check_passed"
        mock_fetch.assert_called_once_with(node="pr_pre_checker")
        mock_rebase.assert_called_once_with("origin/main", node="pr_pre_checker")

    @patch("copium_loop.nodes.pr_pre_checker.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.os.path.exists")
    @patch("copium_loop.nodes.pr_pre_checker.get_telemetry")
    async def test_pr_pre_checker_telemetry(
        self,
        mock_get_telemetry,
        mock_exists,
        mock_rebase,
        _mock_fetch,
        mock_is_dirty,
        mock_get_branch,
    ):
        mock_exists.return_value = True
        mock_get_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_rebase.return_value = {"exit_code": 0, "output": "Successfully rebased"}
        mock_telemetry = mock_get_telemetry.return_value

        state: AgentState = {"retry_count": 0}
        await pr_pre_checker(state)

        mock_telemetry.log_status.assert_any_call("pr_pre_checker", "active")
        mock_telemetry.log_output.assert_any_call("pr_pre_checker", "--- PR Pre-Checker Node ---\n")
        mock_telemetry.log_status.assert_any_call("pr_pre_checker", "success")

    @patch("copium_loop.nodes.pr_pre_checker.os.path.exists")
    async def test_pr_pre_checker_no_git(self, mock_exists):
        mock_exists.return_value = False
        state: AgentState = {"retry_count": 0}
        result = await pr_pre_checker(state)
        assert result["review_status"] == "pr_skipped"

    @patch("copium_loop.nodes.pr_pre_checker.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.os.path.exists")
    async def test_pr_pre_checker_on_main(self, mock_exists, mock_get_branch):
        mock_exists.return_value = True
        mock_get_branch.return_value = "main"
        state: AgentState = {"retry_count": 0}
        result = await pr_pre_checker(state)
        assert result["review_status"] == "pr_skipped"

    @patch("copium_loop.nodes.pr_pre_checker.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.os.path.exists")
    async def test_pr_pre_checker_dirty(self, mock_exists, mock_is_dirty, mock_get_branch):
        mock_exists.return_value = True
        mock_get_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = True
        state: AgentState = {"retry_count": 0}
        result = await pr_pre_checker(state)
        assert result["review_status"] == "needs_commit"

    @patch("copium_loop.nodes.pr_pre_checker.get_current_branch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.is_dirty", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.fetch", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.rebase", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.rebase_abort", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.notify", new_callable=AsyncMock)
    @patch("copium_loop.nodes.pr_pre_checker.os.path.exists")
    async def test_pr_pre_checker_rebase_fail(
        self,
        mock_exists,
        mock_notify,
        mock_abort,
        mock_rebase,
        mock_fetch,
        mock_is_dirty,
        mock_get_branch,
    ):
        mock_exists.return_value = True
        mock_get_branch.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_rebase.return_value = {"exit_code": 1, "output": "Conflict"}

        state: AgentState = {"retry_count": 0}
        result = await pr_pre_checker(state)

        assert result["review_status"] == "pr_failed"
        mock_fetch.assert_called_once_with(node="pr_pre_checker")
        mock_abort.assert_called_once_with(node="pr_pre_checker")
        mock_notify.assert_called_once()
