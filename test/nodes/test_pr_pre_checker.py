import sys
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import pr_pre_checker

# Get the module object explicitly to avoid shadowing issues
pr_pre_checker_module = sys.modules["copium_loop.nodes.pr_pre_checker_node"]


@pytest.mark.asyncio
class TestPRPreChecker:
    @patch.object(pr_pre_checker_module, "validate_git_context", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "is_dirty", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "fetch", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "rebase", new_callable=AsyncMock)
    async def test_pr_pre_checker_success(
        self, mock_rebase, mock_fetch, mock_is_dirty, mock_validate_git, agent_state
    ):
        mock_validate_git.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_rebase.return_value = {"exit_code": 0, "output": "Successfully rebased"}

        agent_state["retry_count"] = 0
        result = await pr_pre_checker(agent_state)

        assert result["review_status"] == "pre_check_passed"
        mock_fetch.assert_called_once_with(node="pr_pre_checker")
        mock_rebase.assert_called_once_with("origin/main", node="pr_pre_checker")

    @patch.object(pr_pre_checker_module, "validate_git_context", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "is_dirty", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "fetch", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "rebase", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "get_telemetry")
    async def test_pr_pre_checker_telemetry(
        self,
        mock_get_telemetry,
        mock_rebase,
        _mock_fetch,
        mock_is_dirty,
        mock_validate_git,
        agent_state,
    ):
        mock_validate_git.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_rebase.return_value = {"exit_code": 0, "output": "Successfully rebased"}
        mock_telemetry = mock_get_telemetry.return_value

        agent_state["retry_count"] = 0
        await pr_pre_checker(agent_state)

        mock_telemetry.log_status.assert_any_call("pr_pre_checker", "active")
        mock_telemetry.log_output.assert_any_call(
            "pr_pre_checker", "--- PR Pre-Checker Node ---\n"
        )
        mock_telemetry.log_status.assert_any_call("pr_pre_checker", "success")

    @patch.object(pr_pre_checker_module, "validate_git_context", new_callable=AsyncMock)
    async def test_pr_pre_checker_no_git(self, mock_validate_git, agent_state):
        mock_validate_git.return_value = None
        agent_state["retry_count"] = 0
        result = await pr_pre_checker(agent_state)
        assert result["review_status"] == "pr_skipped"

    @patch.object(pr_pre_checker_module, "validate_git_context", new_callable=AsyncMock)
    async def test_pr_pre_checker_on_main(self, mock_validate_git, agent_state):
        mock_validate_git.return_value = None
        agent_state["retry_count"] = 0
        result = await pr_pre_checker(agent_state)
        assert result["review_status"] == "pr_skipped"

    @patch.object(pr_pre_checker_module, "validate_git_context", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "is_dirty", new_callable=AsyncMock)
    async def test_pr_pre_checker_dirty(
        self, mock_is_dirty, mock_validate_git, agent_state
    ):
        mock_validate_git.return_value = "feature-branch"
        mock_is_dirty.return_value = True
        agent_state["retry_count"] = 0
        result = await pr_pre_checker(agent_state)
        assert result["review_status"] == "needs_commit"

    @patch.object(pr_pre_checker_module, "validate_git_context", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "is_dirty", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "fetch", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "rebase", new_callable=AsyncMock)
    @patch.object(pr_pre_checker_module, "rebase_abort", new_callable=AsyncMock)
    async def test_pr_pre_checker_rebase_fail(
        self,
        mock_abort,
        mock_rebase,
        mock_fetch,
        mock_is_dirty,
        mock_validate_git,
        agent_state,
    ):
        mock_validate_git.return_value = "feature-branch"
        mock_is_dirty.return_value = False
        mock_rebase.return_value = {"exit_code": 1, "output": "Conflict"}

        agent_state["retry_count"] = 0
        result = await pr_pre_checker(agent_state)

        assert result["review_status"] == "pr_failed"
        mock_fetch.assert_called_once_with(node="pr_pre_checker")
        mock_abort.assert_called_once_with(node="pr_pre_checker")
