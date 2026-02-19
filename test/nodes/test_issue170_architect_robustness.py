from unittest.mock import MagicMock, patch

import pytest

from copium_loop.nodes.utils import get_architect_prompt
from copium_loop.state import AgentState


@pytest.mark.asyncio
async def test_jules_architect_prompt_robustness():
    """Verify that the Jules architect prompt requires a SUMMARY and specific format."""
    state = AgentState(
        initial_commit_hash="sha123",
    )

    engine = MagicMock()
    engine.sanitize_for_prompt.side_effect = lambda x: x

    with patch("copium_loop.nodes.utils.is_git_repo", return_value=True):
        prompt = await get_architect_prompt("jules", state, engine)

        # New requirements from Issue #170
        assert "SUMMARY: [Your detailed analysis here]" in prompt
        assert "VERDICT: OK" in prompt
        assert "VERDICT: REFACTOR" in prompt
        assert "bulleted list" in prompt.lower()
        assert "technical debt" in prompt.lower()
        assert "architectural violations" in prompt.lower()
        assert "single, final message" in prompt.lower()


@pytest.mark.asyncio
async def test_coder_receives_consolidated_architect_feedback():
    """Verify that the coder node's prompt includes the full architect feedback."""
    from unittest.mock import MagicMock

    from langchain_core.messages import HumanMessage, SystemMessage

    from copium_loop.nodes.utils import get_coder_prompt

    engine = MagicMock()
    engine.sanitize_for_prompt.side_effect = lambda x: x

    architect_feedback = """SUMMARY:
- Duplicate SessionManager classes identified in src/engine/base.py and src/session.py.
- Lack of clear interface for the Journaler node.
- Tight coupling between Coder and Tester nodes.

VERDICT: REFACTOR"""

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=architect_feedback),
        ],
        "architect_status": "refactor",
        "code_status": "ok",
        "review_status": "ok",
        "test_output": "PASS",
    }

    prompt = await get_coder_prompt("jules", state, engine)

    assert "<architect_feedback>" in prompt
    assert architect_feedback in prompt
    assert "Duplicate SessionManager classes" in prompt
    assert "VERDICT: REFACTOR" in prompt
