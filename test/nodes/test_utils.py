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


@pytest.mark.asyncio
class TestGetCoderPrompt:
    async def test_get_coder_prompt_jules_tdd(self):
        # Setup state with jules engine
        from unittest.mock import MagicMock

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        message = MagicMock()
        message.content = "Implement feature X"
        state = {
            "messages": [message],
            "engine": engine,
        }

        prompt = await utils.get_coder_prompt("jules", state)

        # Assert Jules-specific TDD prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology:"
            in prompt
        )
        assert "1. Write tests FIRST (Red):" in prompt
        assert "2. Run tests to verify they fail:" in prompt
        assert "3. Write minimal implementation (Green):" in prompt
        assert "### Mandatory Test Types" in prompt
        # Also verify jules push instruction
        assert (
            "You MUST explicitly use 'git push --force' to push your changes to the feature branch."
            in prompt
        )

    async def test_get_coder_prompt_gemini_tdd(self):
        # Setup state with gemini engine
        from unittest.mock import MagicMock

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        message = MagicMock()
        message.content = "Implement feature X"
        state = {
            "messages": [message],
            "engine": engine,
        }

        prompt = await utils.get_coder_prompt("gemini", state)

        # Assert Gemini-specific (original) TDD prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology."
            in prompt
        )
        assert "To do this, you MUST activate the 'tdd-guide' skill" in prompt
        assert "1. Write tests FIRST (they should fail initially)" in prompt
        assert "2. Run tests to verify they fail" in prompt
        assert "3. Write minimal implementation to make tests pass" in prompt

        # Assert Jules-specific TDD prompt is NOT in Gemini prompt
        assert "1. Write tests FIRST (Red):" not in prompt
        assert "### Mandatory Test Types" not in prompt
        # Verify no jules push instruction
        assert (
            "You MUST explicitly use 'git push --force' to push your changes to the feature branch."
            not in prompt
        )
