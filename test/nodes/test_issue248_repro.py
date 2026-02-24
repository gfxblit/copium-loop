from unittest.mock import MagicMock

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.nodes.utils import get_coder_prompt


@pytest.mark.asyncio
async def test_get_coder_prompt_repro_issue_248():
    """
    Reproduction for Issue 248:
    Simulate a workflow state where last_error contains a stale infra error string.
    Set review_status to pr_failed and add a SystemMessage with a rebase conflict.
    Assert that get_coder_prompt correctly selects the rebase conflict, NOT the infra error.
    """
    engine = MagicMock()
    engine.engine_type = "gemini"
    engine.sanitize_for_prompt.side_effect = lambda x: x

    # Stale infra error in last_error (use an existing pattern from is_infrastructure_error)
    stale_infra_error = "All models exhausted: please try again later"

    # New rebase conflict in a SystemMessage
    rebase_conflict = "Automatic rebase on origin/main failed with the following error: CONFLICT (content): Merge conflict in file.py"

    state = {
        "messages": [
            HumanMessage(content="Original request"),
            SystemMessage(content=rebase_conflict),
        ],
        "review_status": "pr_failed",
        "last_error": stale_infra_error,
        "engine": engine,
        "head_hash": "mock_hash",
    }

    prompt = await get_coder_prompt("gemini", state, engine)

    # If it's broken, it might mention the infra error instead of the rebase conflict
    # because it might be using last_error incorrectly or prioritizing the wrong thing.

    assert "Automatic rebase on origin/main failed" in prompt
    assert "CONFLICT (content)" in prompt
    assert "Infrastructure error" not in prompt
