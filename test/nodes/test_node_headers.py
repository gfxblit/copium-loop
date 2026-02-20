from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import HumanMessage

from copium_loop.nodes.architect_node import architect_node
from copium_loop.nodes.coder_node import coder_node
from copium_loop.nodes.journaler_node import journaler_node
from copium_loop.nodes.pr_creator_node import pr_creator_node
from copium_loop.nodes.pr_pre_checker_node import pr_pre_checker_node
from copium_loop.nodes.reviewer_node import reviewer_node
from copium_loop.nodes.tester_node import tester_node
from copium_loop.telemetry import get_telemetry


@pytest.mark.asyncio
async def test_coder_node_header(agent_state, capsys):
    """Test that coder_node prints and logs its header."""
    agent_state["messages"] = [HumanMessage(content="Build a login form")]
    agent_state["engine"].invoke = AsyncMock(return_value="Mocked Code")

    await coder_node(agent_state)

    captured = capsys.readouterr()
    assert "--- Coder Node ---" in captured.out

    telemetry = get_telemetry()
    logs = telemetry.read_log()
    header_logs = [
        e
        for e in logs
        if e.get("event_type") == "info" and "--- Coder Node ---" in e.get("data", "")
    ]
    assert len(header_logs) > 0


@pytest.mark.asyncio
async def test_architect_node_header(agent_state, capsys):
    """Test that architect_node prints and logs its header."""
    agent_state["engine"].invoke = AsyncMock(return_value="VERDICT: OK")

    await architect_node(agent_state)

    captured = capsys.readouterr()
    assert "--- Architect Node ---" in captured.out

    telemetry = get_telemetry()
    logs = telemetry.read_log()
    header_logs = [
        e
        for e in logs
        if e.get("event_type") == "info"
        and "--- Architect Node ---" in e.get("data", "")
    ]
    assert len(header_logs) > 0


@pytest.mark.asyncio
async def test_tester_node_header(agent_state, capsys):
    """Test that tester_node prints and logs its header."""
    with patch(
        "copium_loop.nodes.tester_node.run_command", new_callable=AsyncMock
    ) as mock_run:
        mock_run.return_value = {"output": "Success", "exit_code": 0}
        await tester_node(agent_state)

    captured = capsys.readouterr()
    assert "--- Tester Node ---" in captured.out

    telemetry = get_telemetry()
    logs = telemetry.read_log()
    header_logs = [
        e
        for e in logs
        if e.get("event_type") == "info" and "--- Tester Node ---" in e.get("data", "")
    ]
    assert len(header_logs) > 0


@pytest.mark.asyncio
async def test_reviewer_node_header(agent_state, capsys):
    """Test that reviewer_node prints and logs its header."""
    agent_state["engine"].invoke = AsyncMock(return_value="VERDICT: APPROVED")

    await reviewer_node(agent_state)

    captured = capsys.readouterr()
    assert "--- Reviewer Node ---" in captured.out

    telemetry = get_telemetry()
    logs = telemetry.read_log()
    header_logs = [
        e
        for e in logs
        if e.get("event_type") == "info"
        and "--- Reviewer Node ---" in e.get("data", "")
    ]
    assert len(header_logs) > 0


@pytest.mark.asyncio
async def test_pr_pre_checker_node_header(agent_state, capsys):
    """Test that pr_pre_checker_node prints and logs its header."""
    with (
        patch(
            "copium_loop.nodes.pr_pre_checker_node.validate_git_context",
            new_callable=AsyncMock,
        ) as mock_validate,
        patch(
            "copium_loop.nodes.pr_pre_checker_node.is_dirty", new_callable=AsyncMock
        ) as mock_dirty,
        patch("copium_loop.nodes.pr_pre_checker_node.fetch", new_callable=AsyncMock),
        patch(
            "copium_loop.nodes.pr_pre_checker_node.rebase", new_callable=AsyncMock
        ) as mock_rebase,
    ):
        mock_validate.return_value = "main"
        mock_dirty.return_value = False
        mock_rebase.return_value = {"exit_code": 0, "output": ""}

        await pr_pre_checker_node(agent_state)

    captured = capsys.readouterr()
    assert "--- PR Pre-Checker Node ---" in captured.out

    telemetry = get_telemetry()
    logs = telemetry.read_log()
    header_logs = [
        e
        for e in logs
        if e.get("event_type") == "info"
        and "--- PR Pre-Checker Node ---" in e.get("data", "")
    ]
    assert len(header_logs) > 0


@pytest.mark.asyncio
async def test_journaler_node_header(agent_state, capsys):
    """Test that journaler_node prints and logs its header."""
    agent_state["engine"].invoke = AsyncMock(return_value="Lesson Learned")
    with patch("copium_loop.nodes.journaler_node.MemoryManager") as mock_memory:
        mock_memory.return_value.get_project_memories.return_value = []
        await journaler_node(agent_state)

    captured = capsys.readouterr()
    assert "--- Journaler Node ---" in captured.out

    telemetry = get_telemetry()
    logs = telemetry.read_log()
    header_logs = [
        e
        for e in logs
        if e.get("event_type") == "info"
        and "--- Journaler Node ---" in e.get("data", "")
    ]
    assert len(header_logs) > 0


@pytest.mark.asyncio
async def test_pr_creator_node_header(agent_state, capsys):
    """Test that pr_creator_node prints and logs its header."""
    with (
        patch(
            "copium_loop.nodes.pr_creator_node.validate_git_context",
            new_callable=AsyncMock,
        ) as mock_validate,
        patch(
            "copium_loop.nodes.pr_creator_node.is_dirty", new_callable=AsyncMock
        ) as mock_dirty,
        patch(
            "copium_loop.nodes.pr_creator_node.push", new_callable=AsyncMock
        ) as mock_push,
        patch(
            "copium_loop.nodes.pr_creator_node.run_command", new_callable=AsyncMock
        ) as mock_run,
    ):
        mock_validate.return_value = "main"
        mock_dirty.return_value = False
        mock_push.return_value = {"exit_code": 0, "output": ""}
        mock_run.return_value = {"exit_code": 0, "output": "https://github.com/pr/1"}

        await pr_creator_node(agent_state)

    captured = capsys.readouterr()
    assert "--- PR Creator Node ---" in captured.out

    telemetry = get_telemetry()
    logs = telemetry.read_log()
    header_logs = [
        e
        for e in logs
        if e.get("event_type") == "info"
        and "--- PR Creator Node ---" in e.get("data", "")
    ]
    assert len(header_logs) > 0
