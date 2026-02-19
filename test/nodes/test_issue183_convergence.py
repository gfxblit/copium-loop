import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.nodes import utils

# Get the module object explicitly to avoid shadowing issues
utils_module = sys.modules["copium_loop.nodes.utils"]


@pytest.mark.asyncio
class TestIssue183Repro:
    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_get_head_hash_utility_exists(self, _mock_resolve_ref, _mock_is_git):
        # Ensure function exists
        assert hasattr(utils, "get_head_hash")

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_architect_prompt_contains_head_hash_for_jules(
        self, mock_resolve_ref, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "deadbeef"
        state = {"initial_commit_hash": "abc"}

        prompt = await utils.get_architect_prompt("jules", state)

        assert "(Current HEAD: deadbeef)" in prompt

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_reviewer_prompt_contains_head_hash_for_jules(
        self, mock_resolve_ref, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "deadbeef"
        state = {"initial_commit_hash": "abc"}

        prompt = await utils.get_reviewer_prompt("jules", state)

        assert "(Current HEAD: deadbeef)" in prompt

    @patch.object(utils_module, "is_git_repo", new_callable=AsyncMock)
    @patch.object(utils_module, "resolve_ref", new_callable=AsyncMock)
    async def test_coder_prompt_contains_head_hash_for_all_engines(
        self, mock_resolve_ref, mock_is_git
    ):
        mock_is_git.return_value = True
        mock_resolve_ref.return_value = "deadbeef"

        engine = MagicMock()
        engine.sanitize_for_prompt.side_effect = lambda x: x
        message = MagicMock()
        message.content = "Implement feature X"
        state = {
            "messages": [message],
            "engine": engine,
        }

        # Test Jules
        prompt_jules = await utils.get_coder_prompt("jules", state, engine)
        assert "(Current HEAD: deadbeef)" in prompt_jules

        # Test Gemini
        prompt_gemini = await utils.get_coder_prompt("gemini", state, engine)
        assert "(Current HEAD: deadbeef)" in prompt_gemini

    @patch("copium_loop.nodes.journaler_node.get_head_hash", new_callable=AsyncMock)
    @patch("copium_loop.nodes.journaler_node.MemoryManager")
    @patch("copium_loop.nodes.journaler_node.get_telemetry")
    async def test_journaler_prompt_contains_head_hash(
        self, _mock_get_telemetry, _mock_memory_manager, mock_get_head_hash
    ):
        from copium_loop.nodes.journaler_node import journaler_node

        mock_get_head_hash.return_value = "deadbeef"
        state = {
            "engine_type": "gemini",
            "test_output": "out",
            "review_status": "rev",
            "git_diff": "diff",
            "verbose": False,
        }
        engine = MagicMock()
        engine.invoke = AsyncMock(return_value="NO_LESSON")

        await journaler_node(state, engine)

        args, _ = engine.invoke.call_args
        prompt = args[0]
        assert "(Current HEAD: deadbeef)" in prompt
