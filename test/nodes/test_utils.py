import sys
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.nodes import utils

# Get the module object explicitly to avoid shadowing issues
utils_module = sys.modules["copium_loop.nodes.utils"]


@pytest.mark.asyncio
class TestValidateGitContext:
    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_telemetry")
    async def test_validate_git_context_no_git(self, mock_get_telemetry, mock_is_git):
        mock_is_git.return_value = False
        mock_telemetry = mock_get_telemetry.return_value

        result = await utils.validate_git_context("test_node")

        assert result is None
        mock_telemetry.log_output.assert_called_with(
            "test_node", "Not a git repository. Skipping PR creation.\n"
        )
        mock_telemetry.log_status.assert_called_with("test_node", "success")

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_current_branch", new_callable=AsyncMock)
    @patch.object(utils_module, "get_telemetry")
    async def test_validate_git_context_main_branch(
        self, mock_get_telemetry, mock_get_branch, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_get_branch.return_value = "main"
        mock_telemetry = mock_get_telemetry.return_value

        result = await utils.validate_git_context("test_node")

        assert result is None
        mock_telemetry.log_output.assert_called_with(
            "test_node", "Not on a feature branch. Skipping PR creation.\n"
        )
        mock_telemetry.log_status.assert_called_with("test_node", "success")

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_current_branch", new_callable=AsyncMock)
    @patch.object(utils_module, "get_telemetry")
    async def test_validate_git_context_feature_branch(
        self, mock_get_telemetry, mock_get_branch, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_get_branch.return_value = "feature-branch"
        mock_telemetry = mock_get_telemetry.return_value

        result = await utils.validate_git_context("test_node")

        assert result == "feature-branch"
        mock_telemetry.log_output.assert_called_with(
            "test_node", "On feature branch: feature-branch\n"
        )
