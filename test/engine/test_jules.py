import hashlib
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from copium_loop.engine.base import LLMError
from copium_loop.engine.jules import (
    MAX_API_RETRIES,
    JulesEngine,
    JulesSessionError,
    JulesTimeoutError,
)


@pytest.mark.asyncio
async def test_poll_session_verdict_preservation():
    """Verify that _poll_session preserves a verdict buried in a description and doesn't overwrite it with generic text."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("builtins.print"),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock activity responses
        client.get.side_effect = [
            # First poll for activities
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Reviewing code",
                                "description": "User's Goal: ... Analysis: ... VERDICT: REFACTOR because of reasons.",
                            },
                        }
                    ]
                },
            ),
            # First poll for session state (STILL RUNNING to allow second poll)
            httpx.Response(200, json={"state": "RUNNING"}),
            # Second poll for activities
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Reviewing code",
                                "description": "User's Goal: ... Analysis: ... VERDICT: REFACTOR because of reasons.",
                            },
                        },
                        {"id": "act2", "sessionCompleted": {}},
                    ]
                },
            ),
            # Second poll for session state (COMPLETED)
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        status_data = await engine._poll_session(
            client,
            "sessions/sess_123",
            timeout=10,
            inactivity_timeout=5,
            node="test_node",
            verbose=True,
        )

        # The summary should be from act1 because it contains VERDICT: REFACTOR
        # even though act2 came after it.
        assert "activities" in status_data
        summary = status_data["activities"][0]["description"]
        assert "VERDICT: REFACTOR" in summary
        assert "Session completed" not in summary


@pytest.mark.asyncio
async def test_poll_session_verdict_anywhere_in_text():
    """Verify that 'VERDICT:' anywhere in text is preserved."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("builtins.print"),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        client.get.side_effect = [
            # First poll: Verdict in title
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Final Verdict: VERDICT: OK",
                            },
                        }
                    ]
                },
            ),
            httpx.Response(200, json={"state": "RUNNING"}),
            # Second poll: Generic description
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Final Verdict: VERDICT: OK",
                            },
                        },
                        {
                            "id": "act2",
                            "progressUpdated": {
                                "description": "Cleaning up resources..."
                            },
                        },
                    ]
                },
            ),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        status_data = await engine._poll_session(
            client, "sessions/sess_123", timeout=10, inactivity_timeout=5
        )

        summary = status_data["activities"][0]["description"]
        assert "VERDICT: OK" in summary
        assert "Cleaning up" not in summary


@pytest.mark.asyncio
async def test_poll_session_verdict_in_agent_messaged_text():
    """Verify that _poll_session extracts verdict from agentMessaged.text."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("builtins.print"),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        client.get.side_effect = [
            # First poll: agentMessaged with text instead of message
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "agentMessaged": {
                                "text": "VERDICT: APPROVED",
                            },
                        }
                    ]
                },
            ),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        status_data = await engine._poll_session(
            client, "sessions/sess_123", timeout=10, inactivity_timeout=5
        )

        summary = status_data["activities"][0]["description"]
        assert "VERDICT: APPROVED" in summary


@pytest.mark.asyncio
async def test_poll_session_verdict_in_top_level_text():
    """Verify that _poll_session extracts verdict from top-level text field."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("builtins.print"),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        client.get.side_effect = [
            # First poll: Top-level text only
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "text": "VERDICT: REJECTED",
                        }
                    ]
                },
            ),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        status_data = await engine._poll_session(
            client, "sessions/sess_123", timeout=10, inactivity_timeout=5
        )

        summary = status_data["activities"][0]["description"]
        assert "VERDICT: REJECTED" in summary


@pytest.mark.asyncio
async def test_jules_prompt_hashing():
    """Verify that JulesEngine correctly hashes prompts for session resumption."""
    engine = JulesEngine()
    prompt = "Test prompt with <html> tags & special chars."
    # Sanitize should happen before hashing
    safe_prompt = engine.sanitize_for_prompt(prompt)
    expected_hash = hashlib.sha256(safe_prompt.encode("utf-8")).hexdigest()

    mock_session_manager = MagicMock()
    engine.session_manager = mock_session_manager

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        mock_push.return_value = {"exit_code": 0, "output": ""}
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine.invoke(prompt, node="coder")

        # Verify that session manager was called with the correct hash
        mock_session_manager.update_jules_session.assert_called_once()
        args, kwargs = mock_session_manager.update_jules_session.call_args
        assert args[0] == "coder"
        assert args[1] == "sessions/sess_123"
        assert kwargs["prompt_hash"] == expected_hash


@pytest.mark.asyncio
async def test_jules_prompt_hashing_different_prompt():
    """Verify that different prompts result in different hashes."""
    engine = JulesEngine()
    hash1 = hashlib.sha256(
        engine.sanitize_for_prompt("Prompt 1").encode("utf-8")
    ).hexdigest()
    hash2 = hashlib.sha256(
        engine.sanitize_for_prompt("Prompt 2").encode("utf-8")
    ).hexdigest()

    assert hash1 != hash2


@pytest.mark.asyncio
async def test_jules_prompt_hashing_same_prompt_resumes():
    """Verify that using the same prompt resumes the session."""
    engine = JulesEngine()
    prompt = "Resume me"
    safe_prompt = engine.sanitize_for_prompt(prompt)
    prompt_hash = hashlib.sha256(safe_prompt.encode("utf-8")).hexdigest()

    mock_session_manager = MagicMock()
    engine.session_manager = mock_session_manager
    # Pre-populate session manager with an existing session
    mock_session_manager.get_engine_state.return_value = {
        "session_id": "sessions/existing_sess",
        "prompt_hash": prompt_hash,
    }

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session polling (it should check the existing session first)
        client.get.side_effect = [
            httpx.Response(200, json={"state": "ACTIVE"}),  # Session check
            httpx.Response(200, json={"activities": []}),  # Activity poll
            httpx.Response(
                200, json={"state": "COMPLETED", "outputs": []}
            ),  # State poll
        ]

        await engine.invoke(prompt, node="coder")

        # client.post (session creation) should NOT have been called
        assert client.post.call_count == 0
        # client.get should have been called for the existing session
        assert client.get.call_count == 3
        args, kwargs = client.get.call_args_list[0]
        assert "existing_sess" in args[0]


@pytest.mark.asyncio
async def test_get_session_url():
    engine = JulesEngine()
    # Test with standard session name
    session_name = "sessions/1278697959791104912"
    expected_url = "https://jules.google.com/session/1278697959791104912"
    assert engine._get_session_url(session_name) == expected_url

    # Test with just ID (though API usually returns sessions/ prefix)
    assert engine._get_session_url("123") == "https://jules.google.com/session/123"


@pytest.mark.asyncio
async def test_jules_invoke_logs_url():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry") as mock_get_telemetry,
        patch("builtins.print") as mock_print,
    ):
        client = mock_client.return_value.__aenter__.return_value
        mock_telemetry = mock_get_telemetry.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(201, json={"name": "sessions/123"})

        # Mock polling
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine.invoke("Test prompt", node="architect", verbose=True)

        expected_url = "https://jules.google.com/session/123"

        # Verify stdout
        mock_print.assert_any_call(f"Jules session created: {expected_url}")

        # Verify telemetry
        mock_telemetry.log_info.assert_any_call(
            "architect", f"Jules session created: {expected_url}\n"
        )


@pytest.mark.asyncio
async def test_jules_poll_session_error_includes_url():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock activity polling (1st) and failing session polling (2nd)
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "FAILED", "name": "sessions/123"}),
        ]

        expected_url = "https://jules.google.com/session/123"
        with pytest.raises(
            JulesSessionError, match=f"Jules session {expected_url} failed"
        ):
            await engine._poll_session(
                client, "sessions/123", timeout=10, inactivity_timeout=5
            )


@pytest.mark.asyncio
async def test_poll_session_extracts_activity_details():
    """Verify that _poll_session extracts title and description from progressUpdated."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("builtins.print"),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        client.get.side_effect = [
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "progressUpdated": {
                                "title": "Step 1",
                                "description": "Doing Step 1",
                            },
                        }
                    ]
                },
            ),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        status_data = await engine._poll_session(
            client, "sessions/sess_123", timeout=10, inactivity_timeout=5
        )

        # In _poll_session, it constructs msg = f"{title}: {display_desc}" if title and desc are present.
        # But here we are checking what _poll_session returns in status_data["activities"][0]["description"]
        # which is actually the last_summary.
        assert status_data["activities"][0]["description"] == "Doing Step 1"


@pytest.mark.asyncio
async def test_jules_agent_messaged_with_text():
    """Verify that agentMessaged activities with 'text' field (no 'message') are handled."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("builtins.print"),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        client.get.side_effect = [
            httpx.Response(
                200,
                json={
                    "activities": [
                        {
                            "id": "act1",
                            "agentMessaged": {
                                "text": "Hello world",
                            },
                        }
                    ]
                },
            ),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        status_data = await engine._poll_session(
            client, "sessions/sess_123", timeout=10, inactivity_timeout=5
        )

        assert status_data["activities"][0]["description"] == "Hello world"


@pytest.mark.asyncio
async def test_jules_api_invoke_success():
    """Verify a successful Jules engine invocation."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="feature-branch"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch(
            "copium_loop.shell.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        mock_push.return_value = {"exit_code": 0, "output": ""}
        mock_stream.return_value = ("output", 0, False, "")
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock activity polling (1st) and session polling success (2nd)
        client.get.side_effect = [
            httpx.Response(
                200,
                json={
                    "activities": [{"id": "done", "description": "Jules API summary"}]
                },
            ),
            httpx.Response(
                200,
                json={
                    "name": "sessions/sess_123",
                    "state": "COMPLETED",
                    "outputs": [
                        {
                            "pullRequest": {
                                "url": "https://github.com/owner/repo/pull/1",
                                "title": "Jules API summary",
                            }
                        }
                    ],
                },
            ),
        ]

        result = await engine.invoke("Test prompt", node="coder")
        assert "Jules API summary" in result
        assert "https://github.com/owner/repo/pull/1" in result

        # Verify pull was called for coder node
        mock_pull.assert_called_once()


@pytest.mark.asyncio
async def test_jules_api_invoke_success_200():
    """Verify that 200 OK for session creation is also treated as success."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="feature-branch"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch(
            "copium_loop.shell.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        mock_push.return_value = {"exit_code": 0, "output": ""}
        mock_stream.return_value = ("output", 0, False, "")
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation with 200 OK
        client.post.return_value = httpx.Response(
            200, json={"name": "sessions/sess_123"}
        )

        # Mock activity polling (1st) and session polling success (2nd)
        client.get.side_effect = [
            httpx.Response(
                200,
                json={
                    "activities": [{"id": "done", "description": "Success with 200"}]
                },
            ),
            httpx.Response(
                200,
                json={
                    "name": "sessions/sess_123",
                    "state": "COMPLETED",
                    "outputs": [],
                },
            ),
        ]

        result = await engine.invoke("Test prompt", node="coder")
        assert result == "Success with 200"
        assert client.post.call_count == 1
        mock_pull.assert_called_once()


@pytest.mark.asyncio
async def test_jules_api_invoke_apply_artifacts():
    """Verify that artifacts are applied when changeSet is present."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("copium_loop.git.add", new_callable=AsyncMock) as mock_add,
        patch("copium_loop.git.commit", new_callable=AsyncMock) as mock_commit,
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch(
            "copium_loop.engine.jules.run_command", new_callable=AsyncMock
        ) as mock_run_command,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        mock_push.return_value = {"exit_code": 0, "output": "Pushed"}
        mock_run_command.return_value = {"exit_code": 0, "output": "Applied"}
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation
        client.post.return_value = httpx.Response(201, json={"name": "sess"})

        # Mock session polling success with changeSet
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(
                200,
                json={
                    "state": "COMPLETED",
                    "outputs": [
                        {
                            "changeSet": {
                                "gitPatch": {
                                    "unidiffPatch": "patch content",
                                    "suggestedCommitMessage": "fix: bug",
                                }
                            }
                        }
                    ],
                },
            ),
        ]

        result = await engine.invoke("Test prompt", node="coder")

        assert result == "Jules task completed, but no summary was found."
        mock_run_command.assert_called_once()
        args, kwargs = mock_run_command.call_args
        assert args[0] == "git"
        assert "apply" in args[1]
        mock_add.assert_called_once()
        mock_commit.assert_called_once_with("fix: bug", node="coder")
        assert mock_push.call_count == 2


@pytest.mark.asyncio
async def test_jules_api_polling_retries():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch(
            "copium_loop.shell.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        mock_push.return_value = {"exit_code": 0, "output": ""}
        mock_stream.return_value = ("output", 0, False, "")
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock multiple polling responses
        client.get.side_effect = [
            # 1st loop
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "ACTIVE"}),
            # 2nd loop
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "ACTIVE"}),
            # 3rd loop
            httpx.Response(
                200, json={"activities": [{"id": "done", "description": "Done"}]}
            ),
            httpx.Response(
                200,
                json={
                    "state": "COMPLETED",
                    "outputs": [],
                },
            ),
        ]

        result = await engine.invoke("Test prompt", node="coder")
        assert result == "Done"
        assert client.get.call_count == 6


@pytest.mark.asyncio
async def test_jules_api_no_pull_for_architect():
    """Verify that pull is NOT called for architect node."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client
        client.post.return_value = httpx.Response(201, json={"name": "sess"})
        client.get.side_effect = [
            httpx.Response(200, json={"activities": [{"id": "1", "text": "ok"}]}),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine.invoke("Test prompt", node="architect")
        mock_pull.assert_not_called()


@pytest.mark.asyncio
async def test_jules_api_failure_state():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock activity polling (1st) and failing session polling (2nd)
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "FAILED", "name": "sessions/sess_123"}),
        ]

        with pytest.raises(
            JulesSessionError,
            match="Jules session https://jules.google.com/session/sess_123 failed",
        ):
            await engine.invoke("Test prompt")


@pytest.mark.asyncio
async def test_jules_api_creation_error():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("copium_loop.engine.jules.wait_exponential", return_value=MagicMock()),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation error
        client.post.return_value = httpx.Response(500, text="Internal Server Error")

        with pytest.raises(
            JulesSessionError, match="Jules session creation failed with status 500"
        ):
            await engine.invoke("Test prompt")


@pytest.mark.asyncio
async def test_jules_api_no_key():
    engine = JulesEngine()
    with (
        patch.dict("os.environ", {}, clear=True),
        pytest.raises(
            JulesSessionError, match="JULES_API_KEY environment variable is not set"
        ),
    ):
        await engine.invoke("Test prompt")


@pytest.mark.asyncio
async def test_jules_api_timeout():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.get_running_loop") as mock_get_loop,
        patch("asyncio.sleep", return_value=None),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock infinite polling
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "ACTIVE"}),
        ] * 5

        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.time.side_effect = [0, 0, 0.5, 1.5, 2.0, 2.5]

        with pytest.raises(JulesTimeoutError, match="Jules operation timed out"):
            await engine.invoke("Test prompt", command_timeout=1)


@pytest.mark.asyncio
async def test_jules_api_network_error_creation():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("copium_loop.engine.jules.wait_exponential", return_value=MagicMock()),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock network error
        client.post.side_effect = httpx.RequestError("Network error")

        with pytest.raises(
            JulesSessionError, match="Network error creating Jules session"
        ):
            await engine.invoke("Test prompt")


@pytest.mark.asyncio
async def test_jules_api_network_error_polling():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        # Mock session creation success
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock network error during activity polling
        client.get.side_effect = httpx.RequestError("Network error")

        with pytest.raises(
            JulesSessionError, match="Network error polling Jules session"
        ):
            await engine.invoke("Test prompt")


@pytest.mark.asyncio
async def test_jules_api_pull_failure():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch(
            "copium_loop.git.pull",
            return_value={"exit_code": 1, "output": "Merge conflict"},
        ),
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch(
            "copium_loop.shell.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_push.return_value = {"exit_code": 0, "output": ""}
        mock_stream.return_value = ("output", 0, False, "")
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        client.get.side_effect = [
            httpx.Response(
                200, json={"activities": [{"id": "done", "description": "Done"}]}
            ),
            httpx.Response(
                200,
                json={
                    "name": "sessions/sess_123",
                    "state": "COMPLETED",
                    "outputs": [],
                },
            ),
        ]

        with pytest.raises(
            LLMError,
            match="Failed to pull changes: Merge conflict",
        ):
            await engine.invoke("Test prompt", node="coder")


@pytest.mark.asyncio
async def test_jules_api_poll_session_logs():
    """Verify that _poll_session logs activities to telemetry and stdout."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry") as mock_get_telemetry,
        patch("builtins.print"),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client
        mock_telemetry = mock_get_telemetry.return_value

        # Mock activity responses
        client.get.side_effect = [
            # First poll for activities
            httpx.Response(
                200,
                json={
                    "activities": [
                        {"id": "act1", "progressUpdated": {"title": "Step 1"}}
                    ]
                },
            ),
            # First poll for session state
            httpx.Response(200, json={"state": "ACTIVE"}),
            # Second poll for activities
            httpx.Response(
                200,
                json={
                    "activities": [
                        {"id": "act1", "progressUpdated": {"title": "Step 1"}},
                        {
                            "id": "act2",
                            "progressUpdated": {
                                "title": "Step 2",
                                "description": "Doing work",
                            },
                        },
                    ]
                },
            ),
            # Second poll for session state
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine._poll_session(
            client,
            "sessions/sess_123",
            timeout=10,
            inactivity_timeout=5,
            node="test_node",
            verbose=True,
        )

        # Verify telemetry calls
        assert mock_telemetry.log_output.call_count == 2
        mock_telemetry.log_output.assert_any_call("test_node", "Step 1\n")
        mock_telemetry.log_output.assert_any_call("test_node", "Step 2: Doing work\n")


def test_jules_engine_sanitize_for_prompt():
    engine = JulesEngine()
    text = "<test_output>some results</test_output>"
    sanitized = engine.sanitize_for_prompt(text)
    assert "[test_output]" in sanitized
    assert "[/test_output]" in sanitized
    assert "<test_output>" not in sanitized

    long_text = "a" * 13000
    sanitized = engine.sanitize_for_prompt(long_text)
    assert len(sanitized) < 13000
    assert "... (truncated for brevity)" in sanitized


@pytest.mark.asyncio
async def test_jules_api_invoke_pushes_branch_for_coder():
    """Verify that git.push is called for coder node when starting a new session."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="feature-branch"),
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        mock_push.return_value = {"exit_code": 0, "output": "Pushed"}
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine.invoke("Test prompt", node="coder")

        mock_push.assert_called_with(
            remote="origin", branch="feature-branch", node="coder"
        )


@pytest.mark.asyncio
async def test_jules_api_invoke_no_push_for_architect():
    """Verify that git.push is NOT called for non-coder nodes."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("copium_loop.git.push", new_callable=AsyncMock) as mock_push,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        mock_push.return_value = {"exit_code": 0, "output": "Pushed"}
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client
        client.post.return_value = httpx.Response(201, json={"name": "sess"})
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "COMPLETED", "outputs": []}),
        ]

        await engine.invoke("Test prompt", node="architect")

        mock_push.assert_not_called()


@pytest.mark.asyncio
async def test_request_with_retry_success_after_failure():
    """Verify that _request_with_retry eventually succeeds after transient failures."""
    engine = JulesEngine()

    with (
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("copium_loop.engine.jules.wait_exponential", return_value=MagicMock()),
    ):
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        mock_client.get.side_effect = [
            httpx.ConnectError("Connection failed"),
            httpx.ConnectError("Connection failed again"),
            httpx.Response(200, json={"success": True}),
        ]

        resp = await engine._request_with_retry(
            "Context", mock_client.get, "http://example.com"
        )
        assert resp.status_code == 200
        assert mock_client.get.call_count == 3


@pytest.mark.asyncio
async def test_request_with_retry_exhaustion():
    """Verify that _request_with_retry raises JulesSessionError after exhausting retries."""
    engine = JulesEngine()

    with (
        patch("asyncio.sleep", return_value=None),
        patch("copium_loop.engine.jules.get_telemetry"),
        patch("copium_loop.engine.jules.wait_exponential", return_value=MagicMock()),
    ):
        mock_client = AsyncMock(spec=httpx.AsyncClient)

        mock_client.get.side_effect = httpx.ConnectError("Permanent failure")

        with pytest.raises(JulesSessionError, match="Context: Permanent failure"):
            await engine._request_with_retry(
                "Context", mock_client.get, "http://example.com"
            )

        assert mock_client.get.call_count == MAX_API_RETRIES


@pytest.mark.asyncio
async def test_jules_api_inactivity_timeout_reset():
    """
    Test that seeing new activities resets the inactivity timer.
    """
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.get_running_loop") as mock_get_loop,
        patch("asyncio.sleep", return_value=None),
    ):
        client = AsyncMock()
        mock_client.return_value.__aenter__.return_value = client

        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),  # 1
            httpx.Response(200, json={"state": "ACTIVE"}),  # 2
            httpx.Response(
                200, json={"activities": [{"id": "act1", "description": "Progress"}]}
            ),  # 3
            httpx.Response(200, json={"state": "ACTIVE"}),  # 4
            httpx.Response(
                200, json={"activities": [{"id": "act1", "description": "Progress"}]}
            ),  # 5
            httpx.Response(200, json={"state": "ACTIVE"}),  # 6
        ]

        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        mock_loop.time.side_effect = [0, 0, 5, 11, 20]

        with pytest.raises(JulesTimeoutError, match="inactivity timeout: 10s"):
            await engine.invoke(
                "Test prompt", command_timeout=100, inactivity_timeout=10
            )

        assert client.get.call_count >= 6
