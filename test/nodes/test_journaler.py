from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.nodes.journaler import journaler
from copium_loop.state import AgentState


@pytest.mark.asyncio
async def test_journaler_success():
    state: AgentState = {
        "messages": [],
        "code_status": "coded",
        "test_output": "All tests passed",
        "review_status": "approved",
        "architect_status": "",
        "retry_count": 0,
        "pr_url": "http://github.com/pr/1",
        "issue_url": "http://github.com/issue/37",
        "initial_commit_hash": "abc",
        "git_diff": "diff content",
        "verbose": False,
        "last_error": ""
    }

    with patch("copium_loop.nodes.journaler.invoke_gemini", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "Always ensure memory is persisted."

        with patch("copium_loop.nodes.journaler.MemoryManager") as mock_memory_manager:
            instance = mock_memory_manager.return_value

            result = await journaler(state)

            assert result["journal_status"] == "journaled"
            assert result["review_status"] == "approved" # Preserved
            instance.log_learning.assert_called_once_with("Always ensure memory is persisted.")

@pytest.mark.asyncio
async def test_journaler_updates_pending_status():
    state: AgentState = {
        "messages": [],
        "code_status": "coded",
        "test_output": "All tests passed",
        "review_status": "pending", # Initial status
        "architect_status": "",
        "retry_count": 0,
        "pr_url": "",
        "issue_url": "",
        "initial_commit_hash": "abc",
        "git_diff": "diff content",
        "verbose": False,
        "last_error": ""
    }

    with patch("copium_loop.nodes.journaler.invoke_gemini", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "A lesson"
        with patch("copium_loop.nodes.journaler.MemoryManager"):
            result = await journaler(state)
            assert result["review_status"] == "journaled"
            mock_invoke.assert_called_once()
            # Verify that the prompt contains some relevant info
            args, kwargs = mock_invoke.call_args
            prompt = args[0]
            assert "diff content" in prompt
            assert "All tests passed" in prompt


@pytest.mark.asyncio
async def test_journaler_includes_telemetry_log():
    state: AgentState = {
        "messages": [],
        "code_status": "coded",
        "test_output": "All tests passed",
        "review_status": "approved",
        "architect_status": "",
        "retry_count": 0,
        "pr_url": "http://github.com/pr/1",
        "issue_url": "http://github.com/issue/37",
        "initial_commit_hash": "abc",
        "git_diff": "diff content",
        "verbose": False,
        "last_error": ""
    }

    with patch("copium_loop.nodes.journaler.invoke_gemini", new_callable=AsyncMock) as mock_invoke:
        mock_invoke.return_value = "Always ensure memory is persisted."

        with patch("copium_loop.nodes.journaler.MemoryManager"), \
             patch("copium_loop.nodes.journaler.get_telemetry") as mock_get_telemetry:
            mock_telemetry = MagicMock()
            mock_get_telemetry.return_value = mock_telemetry

            # Mock get_formatted_log to return a string
            mock_telemetry.get_formatted_log.return_value = (
                "coder: status: active\n"
                "coder: output: Writing some code...\n"
                "tester: status: active\n"
                "tester: output: Running tests..."
            )

            await journaler(state)

            # Verify that the prompt contains telemetry information
            args, _ = mock_invoke.call_args
            prompt = args[0]

            assert "TELEMETRY LOG:" in prompt
            assert "coder: status: active" in prompt
            assert "coder: output: Writing some code..." in prompt
            assert "tester: status: active" in prompt
            assert "tester: output: Running tests..." in prompt


@pytest.mark.asyncio
async def test_journaler_verbosity_and_filtering():
    # Setup
    state = AgentState()
    state["test_output"] = "Tests passed"
    state["review_status"] = "Approved"
    state["git_diff"] = "diff"
    state["verbose"] = False

    # Mock dependencies
    with (
        patch(
            "copium_loop.nodes.journaler.invoke_gemini", new_callable=AsyncMock
        ) as mock_gemini,
        patch("copium_loop.nodes.journaler.MemoryManager") as MockMemoryManager,
    ):
        # Setup MemoryManager mock
        mock_mem_instance = MockMemoryManager.return_value

        # Case 1: Generic/useless lesson (Simulated)
        # If the LLM returns something that is NOT "NO_LESSON", it SHOULD be logged.
        mock_gemini.return_value = "No significant lesson learned."

        await journaler(state)

        mock_mem_instance.log_learning.assert_called_once_with(
            "No significant lesson learned."
        )

        # Reset mock for next case
        mock_mem_instance.reset_mock()

        # Case 2: LLM explicitly returns NO_LESSON
        mock_gemini.return_value = "NO_LESSON"

        await journaler(state)

        # Expectation: log_learning should NOT be called for NO_LESSON
        mock_mem_instance.log_learning.assert_not_called()

        # Case 3: Empty string
        mock_gemini.return_value = ""
        await journaler(state)
        mock_mem_instance.log_learning.assert_not_called()


@pytest.mark.asyncio
async def test_journaler_prompt_content():
    # We want to verify that the prompt sent to Gemini includes instructions about
    # being concise, not being a status report, and the context about tracking overall experience.

    state = AgentState()
    state["test_output"] = "out"
    state["review_status"] = "rev"
    state["git_diff"] = "diff"

    with patch(
        "copium_loop.nodes.journaler.invoke_gemini", new_callable=AsyncMock
    ) as mock_gemini:
        mock_gemini.return_value = "A lesson"  # Needed so lesson.strip() works
        with patch("copium_loop.nodes.journaler.MemoryManager"):
            await journaler(state)

            call_args = mock_gemini.call_args
            prompt = call_args[0][0]

            # Assertions based on requirements
            assert "Strictly NO status reports" in prompt
            assert "save_memory" in prompt
            assert "Global/Experiential Memory" in prompt
            assert '"NO_LESSON"' in prompt


@pytest.mark.asyncio
async def test_journaler_prompt_includes_timestamp_instruction():
    # We want to verify that the prompt sent to Gemini includes instructions about
    # including a timestamp when using save_memory.

    state = AgentState()
    state["test_output"] = "out"
    state["review_status"] = "rev"
    state["git_diff"] = "diff"

    with patch(
        "copium_loop.nodes.journaler.invoke_gemini", new_callable=AsyncMock
    ) as mock_gemini:
        mock_gemini.return_value = "A lesson"
        with patch("copium_loop.nodes.journaler.MemoryManager"):
            await journaler(state)

            call_args = mock_gemini.call_args
            prompt = call_args[0][0]

            # Assertions for the new requirement
            assert "timestamp" in prompt.lower()
            assert "save_memory" in prompt
            # Check for the specific instruction context
            assert "include a timestamp" in prompt.lower() or "ensure there's a timestamp" in prompt.lower()


@pytest.mark.asyncio
async def test_journaler_prompt_includes_existing_memories():
    state = AgentState()
    state["test_output"] = "out"
    state["review_status"] = "rev"
    state["git_diff"] = "diff"

    with patch(
        "copium_loop.nodes.journaler.invoke_gemini", new_callable=AsyncMock
    ) as mock_gemini:
        mock_gemini.return_value = "A lesson"
        with patch("copium_loop.nodes.journaler.MemoryManager") as mock_memory_manager:
            instance = mock_memory_manager.return_value
            instance.get_project_memories.return_value = ["Existing Memory 1", "Existing Memory 2"]
            
            await journaler(state)

            call_args = mock_gemini.call_args
            prompt = call_args[0][0]

            assert "EXISTING PROJECT MEMORIES:" in prompt
            assert "Existing Memory 1" in prompt
            assert "Existing Memory 2" in prompt
            assert "NO_LESSON" in prompt
            assert "redundant" in prompt.lower() or "duplicate" in prompt.lower()
