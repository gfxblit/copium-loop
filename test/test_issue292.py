from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from copium_loop.nodes.utils import get_coder_prompt, handle_node_error
from copium_loop.session_manager import SessionManager


@pytest.fixture
def temp_session_dir(tmp_path):
    """Fixture to provide a temporary directory for session files."""
    with patch("copium_loop.session_manager.Path.home") as mock_home:
        mock_home.return_value = tmp_path
        yield tmp_path / ".copium" / "sessions"


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_session_dir")
async def test_session_manager_message_persistence():
    """
    Test that SessionManager correctly serializes and deserializes LangChain messages.
    This is the core of Issue 292's persistence problem.
    """
    session_id = "test_persistence"
    manager = SessionManager(session_id)

    messages = [
        HumanMessage(content="Implement rust support"),
        SystemMessage(
            content="Automatic rebase on origin/main failed with the following error: CONFLICT"
        ),
        SystemMessage(
            content="All models exhausted. Last error: resource has been exhausted"
        ),
    ]

    state = {"messages": messages, "code_status": "failed", "retry_count": 2}

    # This should now handle LangChain messages
    manager.update_agent_state(state)

    # Verify it's saved to disk (manually inspect JSON if needed)
    assert manager.state_file.exists()

    # Reload in a new manager instance
    new_manager = SessionManager(session_id)
    loaded_state = new_manager.get_agent_state()

    loaded_messages = loaded_state["messages"]
    assert len(loaded_messages) == 3
    assert isinstance(loaded_messages[0], HumanMessage)
    assert isinstance(loaded_messages[1], SystemMessage)
    assert loaded_messages[0].content == "Implement rust support"
    assert "CONFLICT" in loaded_messages[1].content
    assert "resource has been exhausted" in loaded_messages[2].content


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_session_dir")
async def test_session_manager_no_messages():
    """Test that SessionManager handles state without messages."""
    session_id = "test_no_messages"
    manager = SessionManager(session_id)
    state = {"foo": "bar"}
    manager.update_agent_state(state)

    new_manager = SessionManager(session_id)
    assert new_manager.get_agent_state() == state


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_session_dir")
async def test_session_manager_empty_messages():
    """Test that SessionManager handles state with empty messages list."""
    session_id = "test_empty_messages"
    manager = SessionManager(session_id)
    state = {"messages": []}
    manager.update_agent_state(state)

    new_manager = SessionManager(session_id)
    assert new_manager.get_agent_state() == state


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_session_dir")
async def test_session_manager_already_serialized_messages():
    """Test that SessionManager handles state where messages are already dicts."""
    session_id = "test_already_serialized"
    manager = SessionManager(session_id)
    # Use message_to_dict to get a valid serialized message
    messages_dict = [
        {
            "type": "human",
            "data": {"content": "hi", "additional_kwargs": {}, "response_metadata": {}},
        }
    ]
    state = {"messages": messages_dict}
    manager.update_agent_state(state)

    new_manager = SessionManager(session_id)
    loaded_state = new_manager.get_agent_state()
    assert len(loaded_state["messages"]) == 1
    assert isinstance(loaded_state["messages"][0], HumanMessage)
    assert loaded_state["messages"][0].content == "hi"


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_session_dir")
async def test_session_manager_session_info():
    """Test that SessionManager correctly handles sticky session info."""
    session_id = "test_session_info"
    manager = SessionManager(session_id)

    manager.update_session_info(
        branch_name="feature-1",
        repo_root="/tmp/repo",
        engine_name="gemini",
        original_prompt="implement feature 1",
    )

    assert manager.get_branch_name() == "feature-1"
    assert manager.get_repo_root() == "/tmp/repo"
    assert manager.get_engine_name() == "gemini"
    assert manager.get_original_prompt() == "implement feature 1"

    # Reload
    new_manager = SessionManager(session_id)
    assert new_manager.get_branch_name() == "feature-1"
    assert new_manager.get_repo_root() == "/tmp/repo"
    assert new_manager.get_engine_name() == "gemini"
    assert new_manager.get_original_prompt() == "implement feature 1"


def test_handle_node_error_protects_real_errors():
    """
    Test that handle_node_error does not overwrite a 'real' error with an infra error.
    """
    rebase_error = (
        "Automatic rebase on origin/main failed with the following error: CONFLICT"
    )
    infra_error = "All models exhausted. Last error: resource has been exhausted"

    state = {
        "messages": [HumanMessage(content="req")],
        "last_error": rebase_error,
        "retry_count": 1,
    }

    # Simulate an infrastructure failure
    new_state_infra = handle_node_error(
        state, "coder_node", infra_error, status_key="code_status", error_value="failed"
    )

    # Current behavior (FAILING): last_error becomes the infra error
    # Desired behavior: last_error remains the rebase error (or includes it)
    assert rebase_error in new_state_infra["last_error"]


@pytest.mark.asyncio
async def test_get_coder_prompt_prioritization():
    """
    Test that get_coder_prompt prioritizes specific failure states over generic ones.
    """
    engine = MagicMock()
    engine.sanitize_for_prompt.side_effect = lambda x: x

    rebase_error = (
        "Automatic rebase on origin/main failed with the following error: CONFLICT"
    )

    state = {
        "messages": [
            HumanMessage(content="Implement rust support"),
            SystemMessage(content=rebase_error),
        ],
        "review_status": "pr_failed",
        "code_status": "failed",  # Coder crashed or exhausted retries
        "last_error": rebase_error,
        "retry_count": 1,
    }

    # Mock get_head to avoid git calls
    with patch("copium_loop.nodes.utils.get_head", return_value="abc1234"):
        prompt = await get_coder_prompt("gemini", state, engine)

    # Should hit "Your previous attempt to create a PR failed"
    # instead of "Coder encountered an unexpected failure"
    assert "Your previous attempt to create a PR failed" in prompt
    assert "CONFLICT" in prompt
