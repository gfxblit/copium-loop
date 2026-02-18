import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

# We'll need to import from copium_loop.nodes.architect once it exists
from copium_loop.nodes.architect import architect

# Get the module object explicitly to avoid shadowing issues
architect_module = sys.modules["copium_loop.nodes.architect"]


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    type(engine).engine_type = PropertyMock(return_value="gemini")
    engine.invoke = AsyncMock(return_value="VERDICT: OK")
    engine.sanitize_for_prompt = MagicMock(side_effect=lambda x, _max_length=12000: x)
    return engine


class TestArchitectNode:
    """Tests for the architect node."""

    @pytest.fixture(autouse=True)
    def setup_architect_mocks(self):
        """Setup common mocks for architect tests."""
        self.mock_get_diff_patcher = patch(
            "copium_loop.nodes.utils.get_diff", new_callable=AsyncMock
        )
        self.mock_get_diff = self.mock_get_diff_patcher.start()
        self.mock_get_diff.return_value = "diff"

        self.mock_is_git_repo_patcher = patch(
            "copium_loop.nodes.utils.is_git_repo", new_callable=AsyncMock
        )
        self.mock_is_git_repo = self.mock_is_git_repo_patcher.start()
        self.mock_is_git_repo.return_value = True

        yield

        self.mock_get_diff_patcher.stop()
        self.mock_is_git_repo_patcher.stop()

    @pytest.mark.asyncio
    async def test_architect_returns_ok(self, mock_engine):
        """Test that architect returns ok status."""
        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await architect(state)

        assert result["architect_status"] == "ok"
        assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_architect_returns_refactor(self, mock_engine):
        """Test that architect returns refactor status."""
        mock_engine.invoke.return_value = (
            "VERDICT: REFACTOR\nToo many responsibilities in one file."
        )

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await architect(state)

        assert result["architect_status"] == "refactor"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_takes_last_verdict(self, mock_engine):
        """Test that architect takes the last verdict found in the content."""
        mock_engine.invoke.return_value = (
            "VERDICT: REFACTOR\nActually, it is fine.\nVERDICT: OK"
        )

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await architect(state)

        assert result["architect_status"] == "ok"

    @pytest.mark.asyncio
    async def test_architect_returns_error_on_exception(self, mock_engine):
        """Test that architect returns error status on exception."""
        mock_engine.invoke.side_effect = Exception("API Error")

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await architect(state)

        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_returns_error_on_missing_verdict(self, mock_engine):
        """Test that architect returns error status when no verdict is found."""
        mock_engine.invoke.return_value = "I am not sure what to do."

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        result = await architect(state)

        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_includes_git_diff(self, mock_engine):
        """Test that architect includes git diff in the prompt."""
        self.mock_get_diff.return_value = "some diff"

        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        await architect(state)

        mock_engine.invoke.assert_called_once()
        args = mock_engine.invoke.call_args[0]
        assert "some diff" in args[0]

    @pytest.mark.asyncio
    async def test_architect_forbids_file_modifications(self, mock_engine):
        """Test that architect node explicitly forbids filesystem modifications."""
        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        await architect(state)

        mock_engine.invoke.assert_called_once()
        args = mock_engine.invoke.call_args[0]
        system_prompt = args[0]
        assert "MUST NOT use any tools to modify the filesystem" in system_prompt
        assert "write_file" in system_prompt
        assert "replace" in system_prompt

    @pytest.mark.asyncio
    async def test_architect_prompt_contains_solid_principles(self, mock_engine):
        """Test that architect prompt contains all five SOLID principles."""
        state = {
            "test_output": "PASS",
            "retry_count": 0,
            "initial_commit_hash": "abc",
            "engine": mock_engine,
        }
        await architect(state)

        mock_engine.invoke.assert_called_once()
        args = mock_engine.invoke.call_args[0]
        system_prompt = args[0]

        assert "Single Responsibility Principle (SRP)" in system_prompt
        assert "Open/Closed Principle (OCP)" in system_prompt
        assert "Liskov Substitution Principle (LSP)" in system_prompt
        assert "Interface Segregation Principle (ISP)" in system_prompt
        assert "Dependency Inversion Principle (DIP)" in system_prompt

    @pytest.mark.asyncio
    async def test_architect_skips_llm_on_empty_diff(self, mock_engine):
        """Test that architect returns OK immediately if git diff is empty, without invoking LLM."""
        self.mock_get_diff.return_value = ""  # Force empty diff

        state = {
            "initial_commit_hash": "some_hash",
            "retry_count": 0,
            "verbose": False,
            "engine": mock_engine,
        }

        # Run architect node
        result = await architect(state)

        # Verify
        self.mock_get_diff.assert_called_once()
        mock_engine.invoke.assert_not_called()
        assert result["architect_status"] == "ok"
        assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_architect_handles_git_diff_failure(self, mock_engine):
        """Test that architect returns error status on git diff failure."""
        self.mock_get_diff.side_effect = Exception("git diff error")

        state = {
            "initial_commit_hash": "some_hash",
            "retry_count": 0,
            "verbose": False,
            "engine": mock_engine,
        }

        # Run architect node
        result = await architect(state)

        # Verify
        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1
        assert "git diff error" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_architect_handles_missing_initial_hash(self, mock_engine):
        """Test that architect returns error status on missing initial hash in git repo."""
        state = {
            "initial_commit_hash": "",
            "retry_count": 0,
            "verbose": False,
            "engine": mock_engine,
        }

        # Run architect node
        result = await architect(state)

        # Verify
        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1
        assert "Missing initial commit hash" in result["messages"][0].content

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("temp_git_repo")
    async def test_architect_integration(self, mock_engine):
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
            "engine": mock_engine,
        }

        # Run architect node
        result = await architect(state)

        # Verify call args
        args = mock_engine.invoke.call_args[0]
        system_prompt = args[0]

        # Verify that the uncommitted changes are in the prompt
        assert "modified content" in system_prompt
        assert result["architect_status"] == "ok"
