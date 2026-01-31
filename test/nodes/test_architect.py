from unittest.mock import AsyncMock, patch

import pytest

# We'll need to import from copium_loop.nodes.architect once it exists
# For now, we expect it to fail collection which is fine for TDD Red step
from copium_loop.nodes.architect import architect


class TestArchitectNode:
    """Tests for the architect node."""

    @pytest.mark.asyncio
    async def test_architect_returns_ok(self):
        """Test that architect returns ok status."""
        with patch(
            "copium_loop.nodes.architect.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: OK"

            state = {"test_output": "PASS", "retry_count": 0}
            result = await architect(state)

            assert result["architect_status"] == "ok"
            assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_architect_returns_refactor(self):
        """Test that architect returns refactor status."""
        with patch(
            "copium_loop.nodes.architect.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: REFACTOR\nToo many responsibilities in one file."

            state = {"test_output": "PASS", "retry_count": 0}
            result = await architect(state)

            assert result["architect_status"] == "refactor"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_takes_last_verdict(self):
        """Test that architect takes the last verdict found in the content."""
        with patch(
            "copium_loop.nodes.architect.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = (
                "VERDICT: REFACTOR\nActually, it is fine.\nVERDICT: OK"
            )

            state = {"test_output": "PASS", "retry_count": 0}
            result = await architect(state)

            assert result["architect_status"] == "ok"

    @pytest.mark.asyncio
    async def test_architect_returns_error_on_exception(self):
        """Test that architect returns error status on exception."""
        with patch(
            "copium_loop.nodes.architect.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.side_effect = Exception("API Error")

            state = {"test_output": "PASS", "retry_count": 0}
            result = await architect(state)

            assert result["architect_status"] == "error"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_returns_error_on_missing_verdict(self):
        """Test that architect returns error status when no verdict is found."""
        with patch(
            "copium_loop.nodes.architect.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "I am not sure what to do."

            state = {"test_output": "PASS", "retry_count": 0}
            result = await architect(state)

            assert result["architect_status"] == "error"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    @patch("copium_loop.nodes.architect.os.path.exists")
    @patch("copium_loop.nodes.architect.get_diff", new_callable=AsyncMock)
    async def test_architect_includes_git_diff(self, mock_get_diff, mock_exists):
        """Test that architect includes git diff in the prompt."""
        mock_exists.return_value = True
        mock_get_diff.return_value = "some diff"

        with patch(
            "copium_loop.nodes.architect.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: OK"

            state = {
                "test_output": "PASS",
                "retry_count": 0,
                "initial_commit_hash": "abc",
            }
            await architect(state)

            mock_gemini.assert_called_once()
            args = mock_gemini.call_args[0]
            assert "some diff" in args[0]
