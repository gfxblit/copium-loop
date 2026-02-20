import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest

# Import from the nodes package
from copium_loop.nodes import architect
from copium_loop.nodes.utils import get_architect_prompt

# Get the module object explicitly to avoid shadowing issues
architect_module = sys.modules["copium_loop.nodes.architect_node"]


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
    async def test_architect_returns_ok(self, agent_state):
        """Test that architect returns ok status."""
        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await architect(agent_state)

        assert result["architect_status"] == "ok"
        assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_architect_returns_refactor(self, agent_state):
        """Test that architect returns refactor status."""
        agent_state[
            "engine"
        ].invoke.return_value = (
            "VERDICT: REFACTOR\nToo many responsibilities in one file."
        )

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await architect(agent_state)

        assert result["architect_status"] == "refactor"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_takes_last_verdict(self, agent_state):
        """Test that architect takes the last verdict found in the content."""
        agent_state[
            "engine"
        ].invoke.return_value = "VERDICT: REFACTOR\nActually, it is fine.\nVERDICT: OK"

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await architect(agent_state)

        assert result["architect_status"] == "ok"

    @pytest.mark.asyncio
    async def test_architect_returns_error_on_exception(self, agent_state):
        """Test that architect returns error status on exception."""
        agent_state["engine"].invoke.side_effect = Exception("API Error")

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await architect(agent_state)

        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_returns_error_on_missing_verdict(self, agent_state):
        """Test that architect returns error status when no verdict is found."""
        agent_state["engine"].invoke.return_value = "I am not sure what to do."

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        result = await architect(agent_state)

        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_architect_includes_git_diff(self, agent_state):
        """Test that architect includes git diff in the prompt."""
        self.mock_get_diff.return_value = "some diff"

        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        await architect(agent_state)

        agent_state["engine"].invoke.assert_called_once()
        args = agent_state["engine"].invoke.call_args[0]
        assert "some diff" in args[0]

    @pytest.mark.asyncio
    async def test_architect_forbids_file_modifications(self, agent_state):
        """Test that architect node explicitly forbids filesystem modifications."""
        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        await architect(agent_state)

        agent_state["engine"].invoke.assert_called_once()
        args = agent_state["engine"].invoke.call_args[0]
        system_prompt = args[0]
        assert "MUST NOT use any tools to modify the filesystem" in system_prompt
        assert "write_file" in system_prompt
        assert "replace" in system_prompt

    @pytest.mark.asyncio
    async def test_architect_prompt_contains_solid_principles(self, agent_state):
        """Test that architect prompt contains all five SOLID principles."""
        agent_state["test_output"] = "PASS"
        agent_state["initial_commit_hash"] = "abc"
        await architect(agent_state)

        agent_state["engine"].invoke.assert_called_once()
        args = agent_state["engine"].invoke.call_args[0]
        system_prompt = args[0]

        assert "Single Responsibility Principle (SRP)" in system_prompt
        assert "Open/Closed Principle (OCP)" in system_prompt
        assert "Liskov Substitution Principle (LSP)" in system_prompt
        assert "Interface Segregation Principle (ISP)" in system_prompt
        assert "Dependency Inversion Principle (DIP)" in system_prompt

    @pytest.mark.asyncio
    async def test_architect_skips_llm_on_empty_diff(self, agent_state):
        """Test that architect returns OK immediately if git diff is empty, without invoking LLM."""
        self.mock_get_diff.return_value = ""  # Force empty diff

        agent_state["initial_commit_hash"] = "some_hash"

        # Run architect node
        result = await architect(agent_state)

        # Verify
        self.mock_get_diff.assert_called_once()
        agent_state["engine"].invoke.assert_not_called()
        assert result["architect_status"] == "ok"
        assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_architect_handles_git_diff_failure(self, agent_state):
        """Test that architect returns error status on git diff failure."""
        self.mock_get_diff.side_effect = Exception("git diff error")

        agent_state["initial_commit_hash"] = "some_hash"

        # Run architect node
        result = await architect(agent_state)

        # Verify
        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1
        assert "git diff error" in result["messages"][0].content

    @pytest.mark.asyncio
    async def test_architect_handles_missing_initial_hash(self, agent_state):
        """Test that architect returns error status on missing initial hash in git repo."""
        agent_state["initial_commit_hash"] = ""

        # Run architect node
        result = await architect(agent_state)

        # Verify
        assert result["architect_status"] == "error"
        assert result["retry_count"] == 1
        assert "Missing initial commit hash" in result["messages"][0].content

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("temp_git_repo")
    async def test_architect_integration(self, agent_state):
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
        agent_state["initial_commit_hash"] = initial_commit

        # Run architect node
        result = await architect(agent_state)

        # Verify call args
        args = agent_state["engine"].invoke.call_args[0]
        system_prompt = args[0]

        # Verify that the uncommitted changes are in the prompt
        assert "modified content" in system_prompt
        assert result["architect_status"] == "ok"


@pytest.mark.asyncio
async def test_jules_architect_prompt_robustness(agent_state):
    """Verify that the Jules architect prompt requires a SUMMARY and specific format."""
    agent_state["initial_commit_hash"] = "sha123"

    with patch("copium_loop.nodes.utils.is_git_repo", return_value=True):
        prompt = await get_architect_prompt("jules", agent_state, agent_state["engine"])

        # New requirements from Issue #170
        assert "SUMMARY: [Your detailed analysis here]" in prompt
        assert "VERDICT: OK" in prompt
        assert "VERDICT: REFACTOR" in prompt
        assert "bulleted list" in prompt.lower()
        assert "technical debt" in prompt.lower()
        assert "architectural violations" in prompt.lower()
        assert "single, final message" in prompt.lower()


@pytest.mark.asyncio
async def test_coder_receives_consolidated_architect_feedback(agent_state):
    """Verify that the coder node's prompt includes the full architect feedback."""
    from langchain_core.messages import HumanMessage, SystemMessage

    from copium_loop.nodes.utils import get_coder_prompt

    agent_state["engine"].sanitize_for_prompt.side_effect = (
        lambda x, _max_length=12000: x
    )

    architect_feedback = """SUMMARY:
- Duplicate SessionManager classes identified in src/engine/base.py and src/session.py.
- Lack of clear interface for the Journaler node.
- Tight coupling between Coder and Tester nodes.

VERDICT: REFACTOR"""

    agent_state["messages"] = [
        HumanMessage(content="Original request"),
        SystemMessage(content=architect_feedback),
    ]
    agent_state["architect_status"] = "refactor"
    agent_state["code_status"] = "ok"
    agent_state["review_status"] = "ok"
    agent_state["test_output"] = "PASS"

    prompt = await get_coder_prompt("jules", agent_state, agent_state["engine"])

    assert "<architect_feedback>" in prompt
    assert architect_feedback in prompt
    assert "Duplicate SessionManager classes" in prompt
    assert "VERDICT: REFACTOR" in prompt
