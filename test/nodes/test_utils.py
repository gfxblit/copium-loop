import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.nodes import architect, reviewer, utils

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
        mock_telemetry.log_info.assert_called_with(
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
        mock_telemetry.log_info.assert_called_with(
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
        mock_telemetry.log_info.assert_called_with(
            "test_node", "On feature branch: feature-branch\n"
        )


@pytest.mark.asyncio
class TestGetCoderPrompt:
    async def test_get_coder_prompt_jules_tdd(self):
        # Setup state with jules engine
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        message = MagicMock()
        message.content = "Implement feature X"
        state = {"messages": [message], "engine": engine, "head_hash": "abc123"}

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

    async def test_get_coder_prompt_gemini_tdd(self):
        # Setup state with gemini engine
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        message = MagicMock()
        message.content = "Implement feature X"
        state = {"messages": [message], "engine": engine, "head_hash": "abc123"}

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

    async def test_get_coder_prompt_with_git_hash_on_refactor(self):
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        architect_message = MagicMock()
        architect_message.content = "Architect feedback: please refactor"
        state = {
            "messages": [initial_message, architect_message],
            "architect_status": "refactor",
            "head_hash": "abc1234567890",
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

    async def test_get_coder_prompt_on_test_failure(self):
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        state = {
            "messages": [initial_message],
            "test_output": "Tests failed: 1 error",
            "head_hash": "abc1234567890",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "Your previous implementation failed tests." in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    async def test_get_coder_prompt_on_reviewer_rejection(self):
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        reviewer_message = MagicMock()
        reviewer_message.content = "Reviewer feedback: rejected"
        state = {
            "messages": [initial_message, reviewer_message],
            "review_status": "rejected",
            "head_hash": "abc1234567890",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "Your previous implementation was rejected by the reviewer." in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    async def test_get_coder_prompt_on_code_failure(self):
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        error_message = MagicMock()
        error_message.content = "Unexpected error"
        state = {
            "messages": [initial_message, error_message],
            "code_status": "failed",
            "head_hash": "abc1234567890",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "Coder encountered an unexpected failure" in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    async def test_get_coder_prompt_on_pr_failure(self):
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        error_message = MagicMock()
        error_message.content = "PR creation error"
        state = {
            "messages": [initial_message, error_message],
            "review_status": "pr_failed",
            "head_hash": "abc1234567890",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "Your previous attempt to create a PR failed." in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    async def test_get_coder_prompt_on_needs_commit(self):
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        initial_message = MagicMock()
        initial_message.content = "Initial request"
        state = {
            "messages": [initial_message],
            "review_status": "needs_commit",
            "head_hash": "abc1234567890",
        }

        prompt = await utils.get_coder_prompt("jules", state, engine)

        assert "abc1234567890" in prompt
        assert "You have uncommitted changes that prevent PR creation." in prompt
        assert (
            "CRITICAL: You MUST follow Test-Driven Development (TDD) methodology"
            in prompt
        )

    async def test_get_coder_prompt_prioritizes_latest_message_over_stale_last_error(
        self,
    ):
        """Verify fix for issue #248: latest non-infra error preferred over stale infra last_error."""
        mock_engine = MagicMock()
        mock_engine.engine_type = "gemini"
        mock_engine.sanitize_for_prompt.side_effect = lambda x: x

        infra_error = "Connection refused: model server down"
        rebase_error = "Automatic rebase on origin/main failed with the following error: ... conflict ..."

        from langchain_core.messages import SystemMessage

        state = {
            "messages": [
                HumanMessage(content="Implement feature X"),
                SystemMessage(content=rebase_error),
            ],
            "test_output": "",
            "review_status": "pr_failed",
            "architect_status": "pending",
            "code_status": "coded",
            "head_hash": "abcdef123456",
            "last_error": infra_error,  # Stale infra error
            "engine": mock_engine,
        }

        prompt = await utils.get_coder_prompt("gemini", state, mock_engine)

        assert rebase_error in prompt
        assert "transient infrastructure failure" not in prompt
        assert infra_error not in prompt

    async def test_get_coder_prompt_uses_last_error_if_latest_is_infra(self):
        """Verify that if the latest message IS an infra error, but last_error is a REAL error, we use last_error."""
        mock_engine = MagicMock()
        mock_engine.engine_type = "gemini"
        mock_engine.sanitize_for_prompt.side_effect = lambda x: x

        real_error = "SyntaxError: invalid syntax"
        infra_error = "Connection refused"

        from langchain_core.messages import SystemMessage

        state = {
            "messages": [
                HumanMessage(content="Implement feature X"),
                SystemMessage(content=infra_error),
            ],
            "test_output": "",
            "review_status": "pending",
            "architect_status": "pending",
            "code_status": "failed",
            "head_hash": "abcdef123456",
            "last_error": real_error,  # Real error recorded previously
            "engine": mock_engine,
        }

        prompt = await utils.get_coder_prompt("gemini", state, mock_engine)

        assert real_error in prompt
        assert infra_error not in prompt
        assert "transient infrastructure failure" not in prompt


@pytest.mark.asyncio
class TestPromptsExtended:
    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_diff", new_callable=AsyncMock)
    async def test_get_architect_prompt_jules(self, _mock_get_diff, _mock_is_git):
        state = {"initial_commit_hash": "abc"}
        prompt = await utils.get_architect_prompt("jules", state)
        assert "You are a senior software architect" in prompt
        assert "VERDICT: OK" in prompt

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_diff", new_callable=AsyncMock)
    async def test_get_architect_prompt_gemini(self, mock_get_diff, mock_is_git):
        mock_is_git.return_value = True
        mock_get_diff.return_value = "some diff"
        state = {"initial_commit_hash": "abc"}
        prompt = await utils.get_architect_prompt("gemini", state)
        assert "You are a software architect" in prompt
        assert "some diff" in prompt
        assert "VERDICT: OK" in prompt

    async def test_get_architect_prompt_missing_hash(self):
        with pytest.raises(ValueError, match="Missing initial commit hash"):
            await utils.get_architect_prompt("jules", {})

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_diff", new_callable=AsyncMock)
    async def test_get_reviewer_prompt_jules(self, _mock_get_diff, _mock_is_git):
        state = {"initial_commit_hash": "abc"}
        prompt = await utils.get_reviewer_prompt("jules", state)
        assert "You are a Principal Software Engineer" in prompt
        assert "VERDICT: APPROVED" in prompt

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "get_diff", new_callable=AsyncMock)
    async def test_get_reviewer_prompt_gemini(self, mock_get_diff, mock_is_git):
        mock_is_git.return_value = True
        mock_get_diff.return_value = "some diff"
        state = {"initial_commit_hash": "abc"}
        prompt = await utils.get_reviewer_prompt("gemini", state)
        assert "You are a senior reviewer" in prompt
        assert "some diff" in prompt
        assert "VERDICT: APPROVED" in prompt

    async def test_get_reviewer_prompt_missing_hash(self):
        with pytest.raises(ValueError, match="Missing initial commit hash"):
            await utils.get_reviewer_prompt("jules", {})


@pytest.mark.asyncio
async def test_get_architect_prompt_legacy(agent_state):
    """Verify architect prompt generation for different engines."""
    agent_state["initial_commit_hash"] = "sha123"

    # Test Jules prompt
    with patch("copium_loop.nodes.utils.is_git_repo", return_value=True):
        jules_prompt = await utils.get_architect_prompt("jules", agent_state)
        assert "sha123" in jules_prompt
        assert "git diff" in jules_prompt.lower()
        assert "JULES_OUTPUT.txt" not in jules_prompt

    # Test Gemini prompt
    with (
        patch("copium_loop.nodes.utils.is_git_repo", return_value=True),
        patch(
            "copium_loop.nodes.utils.get_diff", return_value="some diff"
        ) as mock_get_diff,
    ):
        gemini_prompt = await utils.get_architect_prompt("gemini", agent_state)
        assert "some diff" in gemini_prompt
        mock_get_diff.assert_called_with("sha123", head=None, node="architect")


@pytest.mark.asyncio
async def test_get_reviewer_prompt_legacy(agent_state):
    """Verify reviewer prompt generation for different engines."""
    agent_state["initial_commit_hash"] = "sha123"
    agent_state["test_output"] = "PASS"

    # Test Jules prompt
    with patch("copium_loop.nodes.utils.is_git_repo", return_value=True):
        jules_prompt = await utils.get_reviewer_prompt("jules", agent_state)
        assert "sha123" in jules_prompt
        assert "git diff" in jules_prompt.lower()
        assert "JULES_OUTPUT.txt" not in jules_prompt

    # Test Gemini prompt
    with (
        patch("copium_loop.nodes.utils.is_git_repo", return_value=True),
        patch(
            "copium_loop.nodes.utils.get_diff", return_value="some diff"
        ) as mock_get_diff,
    ):
        gemini_prompt = await utils.get_reviewer_prompt("gemini", agent_state)
        assert "some diff" in gemini_prompt
        mock_get_diff.assert_called_with("sha123", head=None, node="reviewer")


@pytest.mark.asyncio
async def test_architect_node_engine_agnostic(agent_state):
    """Verify Architect node is engine-agnostic and doesn't use JULES_OUTPUT.txt."""
    agent_state["engine"].engine_type = "jules"
    agent_state["engine"].invoke.return_value = "VERDICT: OK"
    agent_state["messages"] = [HumanMessage(content="test")]
    agent_state["initial_commit_hash"] = "sha123"

    with (
        patch(
            "copium_loop.nodes.architect_node.get_architect_prompt",
            return_value="mock prompt",
        ) as mock_get_prompt,
    ):
        result = await architect(agent_state)

        mock_get_prompt.assert_called_once()
        agent_state["engine"].invoke.assert_called_once()
        args, kwargs = agent_state["engine"].invoke.call_args
        assert args[0] == "mock prompt"
        assert "sync_strategy" not in kwargs
        assert result["architect_status"] == "ok"


@pytest.mark.asyncio
async def test_reviewer_node_engine_agnostic(agent_state):
    """Verify Reviewer node is engine-agnostic and doesn't use JULES_OUTPUT.txt."""
    agent_state["engine"].engine_type = "jules"
    agent_state["engine"].invoke.return_value = "VERDICT: APPROVED"
    agent_state["messages"] = [HumanMessage(content="test")]
    agent_state["initial_commit_hash"] = "sha123"

    with (
        patch(
            "copium_loop.nodes.reviewer_node.get_reviewer_prompt",
            return_value="mock prompt",
        ) as mock_get_prompt,
    ):
        result = await reviewer(agent_state)

        mock_get_prompt.assert_called_once()
        agent_state["engine"].invoke.assert_called_once()
        args, kwargs = agent_state["engine"].invoke.call_args
        assert args[0] == "mock prompt"
        assert "sync_strategy" not in kwargs
        assert result["review_status"] == "approved"


@pytest.mark.asyncio
class TestConvergencePrompts:
    async def test_architect_prompt_contains_head_hash_from_state(self):
        state = {"initial_commit_hash": "abc", "head_hash": "deadbeef"}
        prompt = await utils.get_architect_prompt("jules", state)
        assert "(Current HEAD: deadbeef)" in prompt

    async def test_reviewer_prompt_contains_head_hash_from_state(self):
        state = {"initial_commit_hash": "abc", "head_hash": "deadbeef"}
        prompt = await utils.get_reviewer_prompt("jules", state)
        assert "(Current HEAD: deadbeef)" in prompt

    async def test_coder_prompt_contains_head_hash_from_state(self):
        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        message = MagicMock()
        message.content = "Implement feature X"
        state = {"messages": [message], "engine": engine, "head_hash": "deadbeef"}
        prompt = await utils.get_coder_prompt("jules", state, engine)
        assert "(Current HEAD: deadbeef)" in prompt
