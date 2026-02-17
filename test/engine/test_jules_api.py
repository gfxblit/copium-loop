from unittest.mock import MagicMock, mock_open, patch

import httpx
import pytest

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
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch(
            "copium_loop.engine.jules.get_current_branch", return_value="feature-branch"
        ),
        patch("copium_loop.engine.jules.pull", return_value={"exit_code": 0, "output": ""}) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("builtins.open", mock_open()) as m_open,
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock polling
        client.get.return_value = httpx.Response(
            200,
            json={
                "name": "sessions/sess_123",
                "state": "COMPLETED",
                "outputs": {
                    "summary": "Jules API summary",
                    "pr_url": "https://github.com/owner/repo/pull/1",
                },
            },
        )

        result = await engine.invoke("Test prompt")
        assert "Jules API summary" in result
        assert "https://github.com/owner/repo/pull/1" in result

        # Verify JULES_OUTPUT.txt was written
        m_open.assert_called_once_with("JULES_OUTPUT.txt", "w", encoding="utf-8")
        handle = m_open()
        handle.write.assert_called_once()
        written_content = handle.write.call_args[0][0]
        assert "Jules API summary" in written_content
        assert "https://github.com/owner/repo/pull/1" in written_content

        # Verify pull was called
        mock_pull.assert_called_once()

        # Verify post payload
        args, kwargs = client.post.call_args
        payload = kwargs["json"]
        assert payload["sourceContext"]["repository"] == "owner/repo"
        assert payload["sourceContext"]["branch"] == "feature-branch"


@pytest.mark.asyncio
async def test_jules_api_polling_retries():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.engine.jules.get_current_branch", return_value="main"),
        patch("copium_loop.engine.jules.pull", return_value={"exit_code": 0, "output": ""}) as mock_pull,
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("builtins.open", mock_open()),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock multiple polling responses
        client.get.side_effect = [
            httpx.Response(200, json={"state": "ACTIVE"}),
            httpx.Response(200, json={"state": "ACTIVE"}),
            httpx.Response(
                200, json={"state": "COMPLETED", "outputs": {"summary": "Done"}}
            ),
        ]

        result = await engine.invoke("Test prompt")
        assert result == "Done"
        assert client.get.call_count == 3
        mock_pull.assert_called_once()


@pytest.mark.asyncio
async def test_jules_api_failure_state():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.engine.jules.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock failing polling response
        client.get.return_value = httpx.Response(
            200, json={"state": "FAILED", "name": "sessions/sess_123"}
        )

        with pytest.raises(
            JulesSessionError, match="Jules session sessions/sess_123 failed"
        ):
            await engine.invoke("Test prompt")


@pytest.mark.asyncio
async def test_jules_api_creation_error():
    engine = JulesEngine()

    with (
        patch.dict("os.environ", {"JULES_API_KEY": "test_key"}),
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.engine.jules.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
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
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.engine.jules.get_current_branch", return_value="main"),
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
        client.get.return_value = httpx.Response(200, json={"state": "ACTIVE"})

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
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.engine.jules.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
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
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.engine.jules.get_current_branch", return_value="main"),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation success
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock network error during polling
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
        patch("copium_loop.engine.jules.get_repo_name", return_value="owner/repo"),
        patch("copium_loop.engine.jules.get_current_branch", return_value="main"),
        patch("copium_loop.engine.jules.pull", return_value={"exit_code": 1, "output": "Merge conflict"}),
        patch("httpx.AsyncClient") as mock_client,
        patch("asyncio.sleep", return_value=None),
        patch("builtins.open", mock_open()),
    ):
        client = mock_client.return_value.__aenter__.return_value

        # Mock session creation
        client.post.return_value = httpx.Response(
            201, json={"name": "sessions/sess_123"}
        )

        # Mock polling success
        client.get.return_value = httpx.Response(
            200,
            json={
                "name": "sessions/sess_123",
                "state": "COMPLETED",
                "outputs": {"summary": "Done"},
            },
        )

        with pytest.raises(
            JulesSessionError, match="Failed to pull changes after Jules completion: Merge conflict"
        ):
            await engine.invoke("Test prompt")


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
