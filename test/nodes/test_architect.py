import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest

# We'll need to import from copium_loop.nodes.architect once it exists
from copium_loop.nodes.architect import architect

# Get the module object explicitly to avoid shadowing issues
architect_module = sys.modules["copium_loop.nodes.architect"]


class TestArchitectNode:
    """Tests for the architect node."""

    @pytest.fixture(autouse=True)
    def setup_architect_mocks(self):
        """Setup common mocks for architect tests."""
        self.mock_get_diff_patcher = patch.object(
            architect_module, "get_diff", new_callable=AsyncMock
        )
        self.mock_get_diff = self.mock_get_diff_patcher.start()
        self.mock_get_diff.return_value = "diff"

        self.mock_is_git_repo_patcher = patch.object(
            architect_module, "is_git_repo", new_callable=AsyncMock
        )
        self.mock_is_git_repo = self.mock_is_git_repo_patcher.start()
        self.mock_is_git_repo.return_value = True

        yield

        self.mock_get_diff_patcher.stop()
        self.mock_is_git_repo_patcher.stop()

    @pytest.mark.asyncio
    async def test_architect_returns_ok(self):
        """Test that architect returns ok status."""
        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: OK"

            state = {
                "test_output": "PASS",
                "retry_count": 0,
                "initial_commit_hash": "abc",
            }
            result = await architect(state)

            assert result["architect_status"] == "ok"
            assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_architect_returns_refactor(self):
        """Test that architect returns refactor status."""
        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = (
                "VERDICT: REFACTOR\nToo many responsibilities in one file."
            )

            state = {
                "test_output": "PASS",
                "retry_count": 0,
                "initial_commit_hash": "abc",
            }
            result = await architect(state)

            assert result["architect_status"] == "refactor"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_takes_last_verdict(self):
        """Test that architect takes the last verdict found in the content."""
        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = (
                "VERDICT: REFACTOR\nActually, it is fine.\nVERDICT: OK"
            )

            state = {
                "test_output": "PASS",
                "retry_count": 0,
                "initial_commit_hash": "abc",
            }
            result = await architect(state)

            assert result["architect_status"] == "ok"

    @pytest.mark.asyncio
    async def test_architect_returns_error_on_exception(self):
        """Test that architect returns error status on exception."""
        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.side_effect = Exception("API Error")

            state = {
                "test_output": "PASS",
                "retry_count": 0,
                "initial_commit_hash": "abc",
            }
            result = await architect(state)

            assert result["architect_status"] == "error"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_returns_error_on_missing_verdict(self):
        """Test that architect returns error status when no verdict is found."""
        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "I am not sure what to do."

            state = {
                "test_output": "PASS",
                "retry_count": 0,
                "initial_commit_hash": "abc",
            }
            result = await architect(state)

            assert result["architect_status"] == "error"
            assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_includes_git_diff(self):
        """Test that architect includes git diff in the prompt."""
        self.mock_get_diff.return_value = "some diff"

        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
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

    @pytest.mark.asyncio
    async def test_architect_forbids_file_modifications(self):
        """Test that architect node explicitly forbids filesystem modifications."""
        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
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
            system_prompt = args[0]
            assert "MUST NOT use any tools to modify the filesystem" in system_prompt
            assert "write_file" in system_prompt
            assert "replace" in system_prompt

    @pytest.mark.asyncio
    async def test_architect_skips_llm_on_empty_diff(self):
        """Test that architect returns OK immediately if git diff is empty, without invoking LLM."""
        self.mock_get_diff.return_value = ""  # Force empty diff

        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: OK"

            state = {
                "initial_commit_hash": "some_hash",
                "retry_count": 0,
                "verbose": False,
            }

            # Run architect node
            result = await architect(state)

            # Verify
            self.mock_get_diff.assert_called_once()
            mock_gemini.assert_not_called()
            assert result["architect_status"] == "ok"
            assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_architect_handles_git_diff_failure(self):
        """Test that architect returns error status on git diff failure."""
        self.mock_get_diff.side_effect = Exception("git diff error")

        state = {
            "initial_commit_hash": "some_hash",
            "retry_count": 0,
            "verbose": False,
        }

        # Run architect node
        result = await architect(state)

        # Verify
        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1
        assert "git diff error" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_architect_handles_missing_initial_hash(self):
        """Test that architect returns error status on missing initial hash in git repo."""
        state = {
            "initial_commit_hash": "",
            "retry_count": 0,
            "verbose": False,
        }

        # Run architect node
        result = await architect(state)

        # Verify
        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1
        assert "Missing initial commit hash" in result["messages"][0].content

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("temp_git_repo")
    async def test_architect_integration(self):
        """Test architect node integration with a real git repo and uncommitted changes."""
        # Stop the class-level mocks so we can use real git
        self.mock_get_diff_patcher.stop()

        # Setup repo with uncommitted changes
        with open("test.txt", "w") as f:
            f.write("initial content")
        subprocess.run(["git", "add", "test.txt"], check=True)
        subprocess.run(["git", "commit", "-m", "initial commit", "-q"], check=True)

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        initial_commit = result.stdout.strip()

        with open("test.txt", "w") as f:
            f.write("modified content")

        # Mock state
        state = {
            "initial_commit_hash": initial_commit,
            "retry_count": 0,
            "verbose": False,
        }

        # Mock invoke_gemini
        with patch.object(
            architect_module, "invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini:
            mock_gemini.return_value = "VERDICT: OK"

            # Run architect node
            result = await architect(state)

            # Verify call args
            args = mock_gemini.call_args[0]
            system_prompt = args[0]

            # Verify that the uncommitted changes are in the prompt
            assert "modified content" in system_prompt
            assert result["architect_status"] == "ok"
