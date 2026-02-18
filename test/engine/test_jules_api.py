from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from copium_loop.engine.base import LLMError
from copium_loop.engine.jules import (
    JulesEngine,
    JulesSessionError,
    JulesTimeoutError,
)


@pytest.mark.asyncio
async def test_jules_api_invoke_success():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="feature-branch"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch(
            "copium_loop.shell.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        mock_stream.return_value = ("output", 0, False, "")
        client = mock_client.return_value.__aenter__.return_value

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

        # Verify post payload
        args, kwargs = client.post.call_args
        payload = kwargs["json"]
        assert payload["sourceContext"]["source"] == "sources/github/owner/repo"
        assert (
            payload["sourceContext"]["githubRepoContext"]["startingBranch"]
            == "feature-branch"
        )


@pytest.mark.asyncio
async def test_jules_api_invoke_success_200():
    """Verify that 200 OK for session creation is also treated as success."""
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="feature-branch"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch(
            "copium_loop.shell.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        mock_stream.return_value = ("output", 0, False, "")
        client = mock_client.return_value.__aenter__.return_value

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
async def test_jules_api_polling_retries():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.git.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.git.get_current_branch", return_value="main"),
        patch("copium_loop.git.pull", new_callable=AsyncMock) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch(
            "copium_loop.shell.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_pull.return_value = {"exit_code": 0, "output": ""}
        mock_stream.return_value = ("output", 0, False, "")
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock multiple polling responses (alternating activity and session state polls)
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
        mock_pull.assert_called_once()


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
        client = mock_client.return_value.__aenter__.return_value
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
        client = mock_client.return_value.__aenter__.return_value

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
            JulesSessionError, match="Jules session sessions/sess_123 failed"
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
        client = mock_client.return_value.__aenter__.return_value

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
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock infinite polling (always ACTIVE)
        client.get.side_effect = [
            httpx.Response(200, json={"activities": []}),
            httpx.Response(200, json={"state": "ACTIVE"}),
        ] * 5

        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop
        # Time increases on each call: 0, 0, 0.5, 1.5 (timeout is 1)
        mock_loop.time.side_effect = [0, 0, 0.5, 1.5, 2.0, 2.5]

        with pytest.raises(JulesTimeoutError, match="Jules operation timed out"):
            # We need to pass command_timeout as a kwarg because it's in the signature
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
        client = mock_client.return_value.__aenter__.return_value

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
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation success
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock network error during activity polling (1st call)
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
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch(
            "copium_loop.shell.stream_subprocess", new_callable=AsyncMock
        ) as mock_stream,
    ):
        mock_stream.return_value = ("output", 0, False, "")
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock activity polling (1st) and session polling success (2nd)
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
        patch("builtins.print") as mock_print,
    ):
        client = mock_client.return_value.__aenter__.return_value
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
        mock_telemetry.log_output.assert_any_call(
            "test_node", "[sessions/sess_123] Step 1\n"
        )
        mock_telemetry.log_output.assert_any_call(
            "test_node", "[sessions/sess_123] Step 2: Doing work\n"
        )

        # Verify print calls
        assert mock_print.call_count == 2
        mock_print.assert_any_call("[sessions/sess_123] Step 1")
        mock_print.assert_any_call("[sessions/sess_123] Step 2: Doing work")


def test_jules_engine_sanitize_for_prompt():
    engine = JulesEngine()
    text = "<test_output>some results</test_output>"
    sanitized = engine.sanitize_for_prompt(text)
    assert "[test_output]" in sanitized
    assert "[/test_output]" in sanitized
    assert "<test_output>" not in sanitized

    # Test truncation
    long_text = "a" * 13000
    sanitized = engine.sanitize_for_prompt(long_text)
    assert len(sanitized) < 13000
    assert "... (truncated for brevity)" in sanitized

    # Test empty
    assert engine.sanitize_for_prompt("") == ""
    assert engine.sanitize_for_prompt(None) == ""
