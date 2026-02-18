from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.engine.gemini import GeminiEngine
from copium_loop.engine.jules import JulesEngine
from copium_loop.nodes.architect import architect
from copium_loop.nodes.coder import coder
from copium_loop.nodes.reviewer import reviewer
from copium_loop.state import AgentState


@pytest.mark.asyncio
async def test_engine_type_property():
    """Verify engine_type property on GeminiEngine and JulesEngine."""
    gemini = GeminiEngine()
    jules = JulesEngine()

    assert gemini.engine_type == "gemini"
    assert jules.engine_type == "jules"


@pytest.mark.asyncio
async def test_architect_jules_workflow():
    """Verify Architect node behavior with JulesEngine."""
    mock_engine = MagicMock(spec=JulesEngine)
    type(mock_engine).engine_type = PropertyMock(return_value="jules")
    mock_engine.sanitize_for_prompt.side_effect = lambda x: x
    mock_engine.invoke = AsyncMock(return_value="Review from Jules.")

    state = AgentState(
        messages=[HumanMessage(content="test")],
        engine=mock_engine,
        initial_commit_hash="sha123",
        retry_count=0,
    )

    with (
        patch("copium_loop.nodes.architect.is_git_repo", return_value=True),
        patch(
            "copium_loop.nodes.architect.get_diff", new_callable=AsyncMock
        ) as mock_get_diff,
        patch("pathlib.Path.exists", return_value=True),
        patch("pathlib.Path.read_text", return_value="VERDICT: OK") as mock_read_text,
    ):
        result = await architect(state)

        # Assertions
        mock_get_diff.assert_not_called()
        assert mock_engine.invoke.called
        call_args = mock_engine.invoke.call_args
        assert call_args.kwargs.get("sync_locally") is True
        prompt = call_args.args[0]
        assert "JULES_OUTPUT.txt" in prompt
        assert "sha123" in prompt
        mock_read_text.assert_called()
        assert result["architect_status"] == "ok"


@pytest.mark.asyncio
async def test_reviewer_jules_workflow():
    """Verify Reviewer node behavior with JulesEngine."""
    mock_engine = MagicMock(spec=JulesEngine)
    type(mock_engine).engine_type = PropertyMock(return_value="jules")
    mock_engine.sanitize_for_prompt.side_effect = lambda x: x
    mock_engine.invoke = AsyncMock(return_value="Review from Jules.")

    state = AgentState(
        messages=[HumanMessage(content="test")],
        engine=mock_engine,
        initial_commit_hash="sha123",
        retry_count=0,
        test_output="PASS",
    )

    with (
        patch("copium_loop.nodes.reviewer.is_git_repo", return_value=True),
        patch(
            "copium_loop.nodes.reviewer.get_diff", new_callable=AsyncMock
        ) as mock_get_diff,
        patch("pathlib.Path.exists", return_value=True),
        patch(
            "pathlib.Path.read_text", return_value="VERDICT: APPROVED"
        ) as mock_read_text,
    ):
        result = await reviewer(state)

        mock_get_diff.assert_not_called()
        assert mock_engine.invoke.called
        call_args = mock_engine.invoke.call_args
        prompt = call_args.args[0]
        assert "JULES_OUTPUT.txt" in prompt
        assert "sha123" in prompt
        mock_read_text.assert_called()
        assert result["review_status"] == "approved"


@pytest.mark.asyncio
async def test_coder_prompt_force_push():
    """Verify Coder node prompt includes git push --force instruction."""
    mock_engine = MagicMock(spec=GeminiEngine)
    type(mock_engine).engine_type = PropertyMock(return_value="gemini")
    mock_engine.sanitize_for_prompt.side_effect = lambda x: x
    mock_engine.invoke = AsyncMock(return_value="Code updated.")

    state = AgentState(
        messages=[HumanMessage(content="implement feature")],
        engine=mock_engine,
        initial_commit_hash="sha123",
        retry_count=0,
    )

    await coder(state)
    assert mock_engine.invoke.called
    prompt = mock_engine.invoke.call_args.args[0]
    assert "git push --force" in prompt


@pytest.mark.asyncio
async def test_jules_engine_selective_sync():
    """Verify JulesEngine selective sync logic."""
    engine = JulesEngine(api_base_url="http://mock-api")
    engine._create_session = AsyncMock(return_value="session-123")
    engine._poll_session = AsyncMock(return_value={"state": "COMPLETED"})
    engine._extract_summary = MagicMock(return_value="done")

    with (
        patch(
            "copium_loop.engine.jules.get_repo_name", new_callable=AsyncMock
        ) as mock_get_repo,
        patch(
            "copium_loop.engine.jules.get_current_branch", new_callable=AsyncMock
        ) as mock_get_branch,
        patch("copium_loop.engine.jules.pull", new_callable=AsyncMock) as mock_pull,
        patch(
            "copium_loop.engine.jules.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_get_repo.return_value = "owner/repo"
        mock_get_branch.return_value = "main"
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        mock_stream.return_value = ("output", 0, False, "")

        await engine.invoke("prompt", node="coder", sync_locally=True)
        mock_pull.assert_called_once()
        mock_stream.assert_not_called()

        mock_pull.reset_mock()
        mock_stream.reset_mock()

        await engine.invoke(
            "prompt", node="architect", sync_locally=True, command_timeout=60
        )
        mock_pull.assert_not_called()
        assert mock_stream.call_count == 2

        fetch_call = mock_stream.call_args_list[0]
        assert "fetch" in fetch_call.args[1]

        checkout_call = mock_stream.call_args_list[1]
        assert "checkout" in checkout_call.args[1]
        assert "JULES_OUTPUT.txt" in checkout_call.args[1]
