from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.nodes import utils
from copium_loop.nodes.journaler_node import journaler_node


@pytest.mark.asyncio
class TestIssue183Convergence:
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

    @patch("copium_loop.nodes.journaler_node.MemoryManager")
    @patch("copium_loop.nodes.journaler_node.get_telemetry")
    async def test_journaler_prompt_contains_head_hash_from_state(
        self, _mock_get_telemetry, _mock_memory_manager
    ):
        state = {
            "engine_type": "gemini",
            "test_output": "out",
            "review_status": "rev",
            "git_diff": "diff",
            "verbose": False,
            "head_hash": "deadbeef",
        }
        engine = MagicMock()
        engine.invoke = AsyncMock(return_value="NO_LESSON")

        await journaler_node(state, engine)

        args, _ = engine.invoke.call_args
        prompt = args[0]
        assert "(Current HEAD: deadbeef)" in prompt

    @patch("copium_loop.nodes.utils.get_head", new_callable=AsyncMock)
    async def test_fallback_to_get_head_if_state_missing_hash(self, mock_get_head):
        mock_get_head.return_value = "fallback_hash"
        state = {"initial_commit_hash": "abc"}  # No head_hash

        prompt = await utils.get_architect_prompt("jules", state)
        assert "(Current HEAD: fallback_hash)" in prompt
        mock_get_head.assert_called()
