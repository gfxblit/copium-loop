from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.engine.gemini import GeminiEngine
from copium_loop.nodes.architect_node import architect_node
from copium_loop.nodes.coder_node import coder_node
from copium_loop.state import AgentState


@pytest.mark.asyncio
async def test_issue249_integration_noise_reduction():
    """
    Integration test for issue #249:
    Ensure CoderNode prompt receives clean architect feedback even if
    the underlying gemini tool emits stderr noise during architectural review.
    """
    # 1. Setup state with mock engine
    engine = GeminiEngine()
    state = AgentState(
        messages=[HumanMessage(content="Implement feature X")],
        engine=engine,
        initial_commit_hash="abc1234",
        head_hash="def5678",
        architect_status="active",
        verbose=True,
    )

    # 2. Mock stream_subprocess for ArchitectNode call
    # It should return clean stdout but noisy stderr, and exit_code 0 (success)
    architect_stdout = (
        "Architectural review complete. VERDICT: REFACTOR. Please improve modularity."
    )
    architect_stderr = (
        "[WARNING] Missing gemini extension 'foo'. Some features may be disabled."
    )

    with patch(
        "copium_loop.engine.gemini.stream_subprocess", new_callable=AsyncMock
    ) as mock_stream:
        # Architect call
        mock_stream.return_value = (architect_stdout, architect_stderr, 0, False, "")

        # 3. Run ArchitectNode
        # We need to mock get_diff because ArchitectNode calls get_architect_prompt which calls get_diff
        with patch(
            "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
        ) as mock_diff:
            mock_diff.return_value = "some diff"
            with patch(
                "copium_loop.nodes.utils.is_git_repo", new_callable=AsyncMock
            ) as mock_git_repo:
                mock_git_repo.return_value = True
                result = await architect_node(state)

        # Verify ArchitectNode result is clean
        architect_message = result["messages"][-1].content
        assert architect_stdout in architect_message
        assert architect_stderr not in architect_message
        assert result["architect_status"] == "refactor"

        # 4. Update state with ArchitectNode result and prepare for CoderNode
        state.update(result)
        # In actual workflow, last message is used for feedback if architect_status is refactor
        state["messages"].append(result["messages"][-1])

        # 5. Mock stream_subprocess for CoderNode call
        coder_stdout = "Implementing feature X with better modularity..."
        mock_stream.return_value = (coder_stdout, "", 0, False, "")

        # 6. Run CoderNode and capture the prompt passed to engine.invoke
        with patch.object(engine, "invoke", wraps=engine.invoke) as spy_invoke:
            await coder_node(state)

            # The first call to engine.invoke in coder_node is the one we want to inspect
            # Wait, coder_node calls engine.invoke(system_prompt, ...)
            system_prompt = spy_invoke.call_args[0][0]

            # 7. Assertions: Coder's prompt should contain clean architect feedback
            assert "<architect_feedback>" in system_prompt
            assert architect_stdout in system_prompt
            assert architect_stderr not in system_prompt
