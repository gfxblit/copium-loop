import sys
from unittest.mock import AsyncMock, MagicMock, patch

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
    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_coder_prompt_jules_tdd(self, mock_resolve_ref, mock_is_git):
        # Setup state with jules engine
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "abc123"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        message = MagicMock()
        message.content = "Implement feature X"
        state = {
            "messages": [message],
            "engine": engine,
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        # Assert Jules-specific TDD prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology:"
            in prompt
        )
        assert "1. Write tests FIRST (Red):" in prompt
        assert "2. Run tests to verify they fail:" in prompt
        assert "3. Write minimal implementation (Green):" in prompt
        assert "### Mandatory Test Types" in prompt
        assert (
            "You MUST explicitly use 'git push --force' to push your changes to the feature branch."
            in prompt
        )

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_coder_prompt_gemini_tdd(self, mock_resolve_ref, mock_is_git):
        # Setup state with gemini engine
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "abc123"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        message = MagicMock()
        message.content = "Implement feature X"
        state = {
            "messages": [message],
            "engine": engine,
        }

        prompt = await utils.get_coder_prompt("gemini", state, engine)

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
        assert (
            "You MUST explicitly use 'git push --force' to push your changes to the feature branch."
            not in prompt
        )

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_coder_prompt_with_git_hash_on_refactor(
        self, mock_resolve_ref, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "abc1234567890"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        architect_message = MagicMock()
        architect_message.content = "Architect feedback: please refactor"
        state = {
            "messages": [initial_message, architect_message],
            "architect_status": "refactor",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert (
            "Your previous implementation was flagged for architectural improvement"
            in prompt
        )
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_coder_prompt_on_test_failure(
        self, mock_resolve_ref, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "abc1234567890"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        state = {
            "messages": [initial_message],
            "test_output": "Tests failed: 1 error",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "Your previous implementation failed tests." in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_coder_prompt_on_reviewer_rejection(
        self, mock_resolve_ref, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "abc1234567890"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        reviewer_message = MagicMock()
        reviewer_message.content = "Reviewer feedback: rejected"
        state = {
            "messages": [initial_message, reviewer_message],
            "review_status": "rejected",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "Your previous implementation was rejected by the reviewer." in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_coder_prompt_on_code_failure(
        self, mock_resolve_ref, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "abc1234567890"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        error_message = MagicMock()
        error_message.content = "Unexpected error"
        state = {
            "messages": [initial_message, error_message],
            "code_status": "failed",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "Coder encountered an unexpected failure" in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_coder_prompt_on_pr_failure(self, mock_resolve_ref, mock_is_git):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "abc1234567890"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        error_message = MagicMock()
        error_message.content = "PR creation error"
        state = {
            "messages": [initial_message, error_message],
            "review_status": "pr_failed",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "Your previous attempt to create a PR failed." in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_coder_prompt_on_needs_commit(
        self, mock_resolve_ref, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "abc1234567890"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        state = {
            "messages": [initial_message],
            "review_status": "needs_commit",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "You have uncommitted changes that prevent PR creation." in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )


@pytest.mark.asyncio
class TestPromptsExtended:
    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_diff", new_callable=AsyncMock)
    async def test_get_architect_prompt_jules(self, _mock_get_diff, _mock_is_git):
        state = {"initial_commit_hash": "abc"}
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        prompt = await utils.get_architect_prompt("jules", state, engine)
        assert "You are a senior software architect" in prompt
        assert "VERDICT: OK" in prompt

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_diff", new_callable=AsyncMock)
    async def test_get_architect_prompt_gemini(self, mock_get_diff, mock_is_git):
        mock_is_git.return_value = True
        mock_get_diff.return_value = "some diff"
        state = {"initial_commit_hash": "abc"}
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        prompt = await utils.get_architect_prompt("gemini", state, engine)
        assert "You are a software architect" in prompt
        assert "some diff" in prompt
        assert "VERDICT: OK" in prompt

    async def test_get_architect_prompt_missing_hash(self):
        engine = MagicMock()
        with pytest.raises(ValueError, match="Missing initial commit hash"):
            await utils.get_architect_prompt("jules", {}, engine)

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_diff", new_callable=AsyncMock)
    async def test_get_reviewer_prompt_jules(self, _mock_get_diff, _mock_is_git):
        state = {"initial_commit_hash": "abc"}
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        prompt = await utils.get_reviewer_prompt("jules", state, engine)
        assert "You are a Principal Software Engineer" in prompt
        assert "VERDICT: APPROVED" in prompt

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_diff", new_callable=AsyncMock)
    async def test_get_reviewer_prompt_gemini(self, mock_get_diff, mock_is_git):
        mock_is_git.return_value = True
        mock_get_diff.return_value = "some diff"
        state = {"initial_commit_hash": "abc"}
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        prompt = await utils.get_reviewer_prompt("gemini", state, engine)
        assert "You are a senior reviewer" in prompt
        assert "some diff" in prompt
        assert "VERDICT: APPROVED" in prompt

    async def test_get_reviewer_prompt_missing_hash(self):
        engine = MagicMock()
        with pytest.raises(ValueError, match="Missing initial commit hash"):
            await utils.get_reviewer_prompt("jules", {}, engine)
