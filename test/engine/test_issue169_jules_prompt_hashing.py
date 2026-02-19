from unittest.mock import ANY, AsyncMock, MagicMock, patch

import httpx
import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.fixture
def mock_session_manager():
    """Fixture to create a mocked SessionManager with state."""
    mock_sm = MagicMock()
    stored_state = {}

    def get_engine_state(engine_type, key):
        return stored_state.get(f"{engine_type}:{key}")

    def update_engine_state(engine_type, key, value):
        stored_state[f"{engine_type}:{key}"] = value

    mock_sm.get_engine_state.side_effect = get_engine_state
    mock_sm.update_engine_state.side_effect = update_engine_state
    mock_sm.update_jules_session.side_effect = lambda node, session_id, prompt_hash: (
        update_engine_state(
            "jules", node, {"session_id": session_id, "prompt_hash": prompt_hash}
        )
    )
    return mock_sm


@pytest.fixture
def jules_engine(mock_session_manager):
    """Fixture to create a JulesEngine with a mocked SessionManager."""
    engine = JulesEngine()
    engine.session_manager = mock_session_manager
    return engine


@pytest.fixture
def common_patches():
    """Fixture for common patches used in JulesEngine tests."""
    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        mock_push.return_value = {"exit_code": 0, "output": "Pushed"}
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        client = mock_client.return_value.__aenter__.return_value
        yield client, mock_push, mock_pull


@pytest.mark.asyncio
async def test_jules_prompt_hashing_creates_new_session_if_prompt_differs(
    jules_engine, common_patches
):
    """
    Verify that a new Jules session is created if the prompt changes,
    even if an existing session for the same node is found in SessionManager.
    """
    engine = jules_engine
    client, _, _ = common_patches

    # First call: creates sess_1
    client.post.return_value = httpx.Response(201, json={"name": "sessions/sess_1"})
    client.get.side_effect = [
        httpx.Response(200, json={"activities": []}),
        httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
    ]

    await engine.invoke("Prompt 1", node="coder")
    assert client.post.call_count == 1

    # Second call: Should create sess_2 because prompt differs
    client.post.return_value = httpx.Response(201, json={"name": "sessions/sess_2"})
    client.get.side_effect = [
        # Activity poll for sess_2 (if it was created)
        httpx.Response(200, json={"activities": []}),
        # State poll for sess_2 (if it was created)
        httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
    ]

    await engine.invoke("Prompt 2", node="coder")

    # EXPECTED: client.post.call_count == 2
    assert client.post.call_count == 2


@pytest.mark.asyncio
async def test_jules_prompt_hashing_reuses_session_if_prompt_identical(
    jules_engine, common_patches
):
    """
    Verify that the same Jules session is reused if the prompt is identical.
    """
    engine = jules_engine
    client, _, _ = common_patches

    # First call: creates sess_1
    client.post.return_value = httpx.Response(201, json={"name": "sessions/sess_1"})
    client.get.side_effect = [
        httpx.Response(200, json={"activities": []}),
        httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
    ]

    await engine.invoke("Same Prompt", node="coder")
    assert client.post.call_count == 1

    # Second call: Should reuse sess_1 because prompt is identical
    client.get.side_effect = [
        # Session check for sess_1
        httpx.Response(200, json={"state": "COMPLETED"}),
        # Activity and state polls for sess_1
        httpx.Response(200, json={"activities": []}),
        # State poll for sess_1
        httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
    ]

    await engine.invoke("Same Prompt", node="coder")

    assert client.post.call_count == 1


@pytest.mark.asyncio
async def test_jules_prompt_hashing_starts_new_session_for_old_string_state(
    jules_engine, mock_session_manager, common_patches
):
    """
    Verify that a new Jules session is created if an old-style (string-only)
    engine state is found in SessionManager.
    """
    engine = jules_engine
    client, _, _ = common_patches

    # Force an old-style state
    mock_session_manager.get_engine_state.return_value = "sessions/old_sess"

    # First call: creates sess_new
    client.post.return_value = httpx.Response(201, json={"name": "sessions/sess_new"})
    client.get.side_effect = [
        # No session check for sess_old because we discarded it (now enforced in SessionManager)
        httpx.Response(200, json={"activities": []}),
        httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
    ]

    await engine.invoke("Prompt", node="coder")

    # Verify it created a new session
    assert client.post.call_count == 1
    # Verify it updated SessionManager with the new dict state
    mock_session_manager.update_jules_session.assert_called_with(
        "coder", "sessions/sess_new", prompt_hash=ANY
    )
