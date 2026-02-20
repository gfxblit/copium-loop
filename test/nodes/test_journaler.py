import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.nodes import journaler

# Get the module object explicitly to avoid shadowing issues
journaler_module = sys.modules["copium_loop.nodes.journaler_node"]


@pytest.mark.asyncio
async def test_journaler_success(agent_state):
    agent_state["engine"].invoke.return_value = "Always ensure memory is persisted."
    agent_state["code_status"] = "coded"
    agent_state["test_output"] = "All tests passed"
    agent_state["review_status"] = "approved"
    agent_state["initial_commit_hash"] = "abc"
    agent_state["git_diff"] = "diff content"
    agent_state["pr_url"] = "http://github.com/pr/1"
    agent_state["issue_url"] = "http://github.com/issue/37"

    with patch.object(journaler_module, "MemoryManager") as mock_memory_manager:
        instance = mock_memory_manager.return_value

        result = await journaler(agent_state)

        assert result["journal_status"] == "journaled"
        assert result["review_status"] == "approved"  # Preserved
        instance.log_learning.assert_called_once_with(
            "Always ensure memory is persisted."
        )


@pytest.mark.asyncio
async def test_journaler_updates_pending_status(agent_state):
    agent_state["code_status"] = "coded"
    agent_state["test_output"] = "All tests passed"
    agent_state["review_status"] = "pending"  # Initial status
    agent_state["initial_commit_hash"] = "abc"
    agent_state["git_diff"] = "diff content"

    agent_state["engine"].invoke.return_value = "A lesson"
    with patch.object(journaler_module, "MemoryManager"):
        result = await journaler(agent_state)
        assert result["review_status"] == "journaled"
        agent_state["engine"].invoke.assert_called_once()
        # Verify that the prompt contains some relevant info
        args, kwargs = agent_state["engine"].invoke.call_args
        prompt = args[0]
        assert "diff content" in prompt
        assert "All tests passed" in prompt


@pytest.mark.asyncio
async def test_journaler_includes_telemetry_log(agent_state):
    agent_state["code_status"] = "coded"
    agent_state["test_output"] = "All tests passed"
    agent_state["review_status"] = "approved"
    agent_state["initial_commit_hash"] = "abc"
    agent_state["git_diff"] = "diff content"
    agent_state["pr_url"] = "http://github.com/pr/1"
    agent_state["issue_url"] = "http://github.com/issue/37"

    with (
        patch.object(journaler_module, "MemoryManager"),
        patch.object(journaler_module, "get_telemetry") as mock_get_telemetry,
    ):
        mock_telemetry = MagicMock()
        mock_get_telemetry.return_value = mock_telemetry

        # Mock get_formatted_log to return a string
        mock_telemetry.get_formatted_log.return_value = (
            "coder: status: active\n"
            "coder: output: Writing some code...\n"
            "tester: status: active\n"
            "tester: output: Running tests..."
        )

        await journaler(agent_state)

        # Verify that the prompt contains telemetry information
        args, _ = agent_state["engine"].invoke.call_args
        prompt = args[0]

        assert "TELEMETRY LOG:" in prompt
        assert "coder: status: active" in prompt
        assert "coder: output: Writing some code..." in prompt
        assert "tester: status: active" in prompt
        assert "tester: output: Running tests..." in prompt


@pytest.mark.asyncio
async def test_journaler_verbosity_and_filtering(agent_state):
    # Setup
    agent_state["test_output"] = "Tests passed"
    agent_state["review_status"] = "Approved"
    agent_state["git_diff"] = "diff"
    agent_state["verbose"] = False

    # Mock dependencies
    with patch.object(journaler_module, "MemoryManager") as MockMemoryManager:
        # Setup MemoryManager mock
        mock_mem_instance = MockMemoryManager.return_value

        # Case 1: Generic/useless lesson (Simulated)
        # If the LLM returns something that is NOT "NO_LESSON", it SHOULD be logged.
        agent_state["engine"].invoke.return_value = "No significant lesson learned."

        await journaler(agent_state)

        mock_mem_instance.log_learning.assert_called_once_with(
            "No significant lesson learned."
        )

        # Reset mock for next case
        mock_mem_instance.reset_mock()

        # Case 2: LLM explicitly returns NO_LESSON
        agent_state["engine"].invoke.return_value = "NO_LESSON"

        await journaler(agent_state)

        # Expectation: log_learning should NOT be called for NO_LESSON
        mock_mem_instance.log_learning.assert_not_called()

        # Case 3: Empty string
        agent_state["engine"].invoke.return_value = ""
        await journaler(agent_state)
        mock_mem_instance.log_learning.assert_not_called()


@pytest.mark.asyncio
async def test_journaler_prompt_content(agent_state):
    # We want to verify that the prompt sent to Gemini includes instructions about
    # being concise, not being a status report, and the context about tracking overall experience.

    agent_state["test_output"] = "out"
    agent_state["review_status"] = "rev"
    agent_state["git_diff"] = "diff"
    agent_state["verbose"] = False

    agent_state[
        "engine"
    ].invoke.return_value = "A lesson"  # Needed so lesson.strip() works
    with patch.object(journaler_module, "MemoryManager"):
        await journaler(agent_state)

        call_args = agent_state["engine"].invoke.call_args
        prompt = call_args[0][0]

        # Assertions based on requirements
        assert "Strictly NO status reports" in prompt
        assert "save_memory" in prompt
        assert "Global/Experiential Memory" in prompt
        assert '"NO_LESSON"' in prompt


@pytest.mark.asyncio
async def test_journaler_prompt_includes_timestamp_instruction(agent_state):
    # We want to verify that the prompt sent to Gemini includes instructions about
    # including a timestamp when using save_memory.

    agent_state["test_output"] = "out"
    agent_state["review_status"] = "rev"
    agent_state["git_diff"] = "diff"
    agent_state["verbose"] = False

    agent_state["engine"].invoke.return_value = "A lesson"
    with patch.object(journaler_module, "MemoryManager"):
        await journaler(agent_state)

        call_args = agent_state["engine"].invoke.call_args
        prompt = call_args[0][0]

        # Assertions for the new requirement
        assert "timestamp" in prompt.lower()
        assert "save_memory" in prompt
        # Check for the specific instruction context
        assert (
            "include a timestamp" in prompt.lower()
            or "ensure there's a timestamp" in prompt.lower()
        )


@pytest.mark.asyncio
async def test_journaler_prompt_includes_existing_memories(agent_state):
    agent_state["test_output"] = "out"
    agent_state["review_status"] = "rev"
    agent_state["git_diff"] = "diff"
    agent_state["verbose"] = False

    agent_state["engine"].invoke.return_value = "A lesson"
    with patch.object(journaler_module, "MemoryManager") as mock_memory_manager:
        instance = mock_memory_manager.return_value
        instance.get_project_memories.return_value = [
            "Existing Memory 1",
            "Existing Memory 2",
        ]

        await journaler(agent_state)

        call_args = agent_state["engine"].invoke.call_args
        prompt = call_args[0][0]

        assert "EXISTING PROJECT MEMORIES:" in prompt
        assert "Existing Memory 1" in prompt
        assert "Existing Memory 2" in prompt
        assert "NO_LESSON" in prompt
        assert "redundant" in prompt.lower() or "duplicate" in prompt.lower()


@pytest.mark.asyncio
async def test_journaler_telemetry(agent_state):
    with (
        patch("copium_loop.nodes.utils.get_telemetry") as mock_utils_telemetry,
        patch.object(journaler_module, "get_telemetry") as mock_node_telemetry,
        patch.object(journaler_module, "MemoryManager") as mock_mm,
    ):
        mock_telemetry = MagicMock()
        mock_utils_telemetry.return_value = mock_telemetry
        mock_node_telemetry.return_value = mock_telemetry

        mock_mm_instance = mock_mm.return_value
        mock_mm_instance.get_project_memories.return_value = []
        agent_state["engine"].invoke.return_value = "Remember this."

        agent_state["review_status"] = "pending"
        agent_state["git_diff"] = "diff"
        agent_state["test_output"] = "PASS"

        await journaler(agent_state)

        mock_telemetry.log_status.assert_any_call("journaler", "active")
        mock_telemetry.log_status.assert_any_call("journaler", "journaled")


@pytest.mark.asyncio
async def test_journaler_prompt_bans_changelogs(agent_state):
    agent_state["code_status"] = "coded"
    agent_state["test_output"] = "out"
    agent_state["review_status"] = "rev"
    agent_state["git_diff"] = "diff"

    agent_state["engine"].invoke.return_value = "NO_LESSON"
    with patch.object(journaler_module, "MemoryManager"):
        await journaler(agent_state)

        call_args = agent_state["engine"].invoke.call_args
        prompt = call_args[0][0]

        # Assertions for the new sections
        assert "ANTI-PATTERNS" in prompt
        assert "PRINCIPLES" in prompt

        # Assertions for the examples
        assert "Bad: The journaler node now deduplicates learnings." in prompt
        assert (
            "Good: Deduplicate learnings by checking against existing memories before logging."
            in prompt
        )


@pytest.mark.asyncio
async def test_journaler_handles_engine_invoke_exception_gracefully(agent_state):
    agent_state["code_status"] = "coded"
    agent_state["test_output"] = "All tests passed"
    agent_state["review_status"] = "pending"
    agent_state["initial_commit_hash"] = "abc"
    agent_state["git_diff"] = "diff content"

    # Simulate an exception in engine.invoke
    agent_state["engine"].invoke.side_effect = Exception("Gemini service unavailable")

    # The function should NOT raise an exception
    result = await journaler(agent_state)

    # It should return a valid dict, ideally indicating failure or fallback
    assert "journal_status" in result
    assert result["journal_status"] == "failed"
    # And ensure review_status is not lost or is set to a sensible default
    assert result["review_status"] == "journaled"


@pytest.mark.asyncio
async def test_journaler_handles_memory_manager_exception_gracefully(agent_state):
    agent_state["code_status"] = "coded"
    agent_state["test_output"] = "All tests passed"
    agent_state["review_status"] = "pending"
    agent_state["initial_commit_hash"] = "abc"
    agent_state["git_diff"] = "diff content"

    agent_state["engine"].invoke.return_value = "Critical Lesson"

    # Simulate exception in MemoryManager
    with patch.object(journaler_module, "MemoryManager") as MockMemoryManager:
        mock_instance = MockMemoryManager.return_value
        mock_instance.log_learning.side_effect = Exception("Disk full")

        result = await journaler(agent_state)

        assert result["journal_status"] == "failed"
        assert result["review_status"] == "journaled"


@pytest.mark.asyncio
@patch.object(journaler_module, "MemoryManager")
@patch.object(journaler_module, "get_telemetry")
async def test_journaler_prompt_contains_head_hash_from_state(
    _mock_get_telemetry, _mock_memory_manager, agent_state
):
    agent_state["engine"].invoke = AsyncMock(return_value="NO_LESSON")
    agent_state["head_hash"] = "deadbeef"

    await journaler(agent_state)

    args, _ = agent_state["engine"].invoke.call_args
    prompt = args[0]
    assert "(Current HEAD: deadbeef)" in prompt
