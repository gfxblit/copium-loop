import os
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.session_manager import SessionData, SessionManager


@pytest.mark.asyncio
async def test_session_id_auto_derivation():
    """Test that session ID is automatically derived from repo and branch."""
    import copium_loop.telemetry
    from copium_loop.telemetry import get_telemetry

    # Reset singleton for testing
    copium_loop.telemetry._telemetry_instance = None

    with patch("subprocess.run") as mock_run:
        def side_effect(cmd, **_kwargs):
            if cmd == ["git", "remote", "get-url", "origin"]:
                m = MagicMock()
                m.returncode = 0
                m.stdout = "git@github.com:owner/repo.git\n"
                return m
            if cmd == ["git", "branch", "--show-current"]:
                m = MagicMock()
                m.returncode = 0
                m.stdout = "feature-branch\n"
                return m
            return MagicMock(returncode=1)

        mock_run.side_effect = side_effect

        telemetry = get_telemetry()
        assert telemetry.session_id == "owner-repo/feature-branch"

def test_cli_parser_new_flags():
    """Test that the CLI has the new flags and removed the old ones."""
    # We'll run the CLI with --help and check output
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [sys.executable, "-m", "copium_loop", "--help"],
        capture_output=True,
        text=True,
        env=env,
    )

    # New flags
    assert "--node" in result.stdout
    assert "-n" in result.stdout
    assert "--continue" in result.stdout
    assert "-c" in result.stdout

    # Old flags removed
    assert "--session" not in result.stdout
    assert "--start" not in result.stdout

@pytest.mark.asyncio
async def test_agent_state_persistence():
    """Test that AgentState is persisted after node execution."""
    from copium_loop.copium_loop import WorkflowManager
    from copium_loop.state import AgentState

    wm = WorkflowManager(session_id="test-session")
    wm.session_manager = MagicMock()

    # Mock a node function
    async def mock_node(_state: AgentState):
        return {"code_status": "success"}

    wrapper = wm._wrap_node("coder", mock_node)

    initial_state = {"prompt": "test", "retry_count": 0}
    # In reality _wrap_node calls get_head, so mock it
    with patch("copium_loop.copium_loop.get_head", new_callable=AsyncMock) as mock_head:
        mock_head.return_value = "deadbeef"
        await wrapper(initial_state)

    # Check that update_agent_state was called
    wm.session_manager.update_agent_state.assert_called_once()
    called_state = wm.session_manager.update_agent_state.call_args[0][0]
    assert called_state["code_status"] == "success"
    assert called_state["prompt"] == "test"

def test_session_data_v3_fields():
    """Verify SessionData has the new required fields."""
    data = SessionData(
        session_id="test/branch",
        branch_name="branch",
        repo_root="/tmp/repo",
        engine_name="gemini",
        original_prompt="hello world"
    )
    assert data.session_id == "test/branch"
    assert data.branch_name == "branch"
    assert data.repo_root == "/tmp/repo"
    assert data.engine_name == "gemini"
    assert data.original_prompt == "hello world"

def test_session_data_serialization_v3():
    """Verify SessionData serialization includes new fields."""
    data = SessionData(
        session_id="test/branch",
        branch_name="branch",
        repo_root="/tmp/repo",
        engine_name="gemini",
        original_prompt="hello world",
        agent_state={"foo": "bar"}
    )
    d = data.to_dict()
    assert d["branch_name"] == "branch"
    assert d["repo_root"] == "/tmp/repo"
    assert d["engine_name"] == "gemini"
    assert d["original_prompt"] == "hello world"
    assert d["agent_state"] == {"foo": "bar"}

    data2 = SessionData.from_dict(d)
    assert data2.branch_name == "branch"
    assert data2.repo_root == "/tmp/repo"
    assert data2.engine_name == "gemini"
    assert data2.original_prompt == "hello world"
    assert data2.agent_state == {"foo": "bar"}

def test_session_manager_update_info(tmp_path):
    """Verify SessionManager.update_session_info works."""
    with patch("pathlib.Path.home", return_value=tmp_path):
        sm = SessionManager("test-session")
        sm.update_session_info(
            branch_name="feat/new",
            repo_root="/home/user/repo",
            engine_name="jules",
            original_prompt="fix bugs"
        )

        # Reload to verify persistence
        sm2 = SessionManager("test-session")
        assert sm2.get_branch_name() == "feat/new"
        assert sm2.get_repo_root() == "/home/user/repo"
        assert sm2.get_engine_name() == "jules"
        assert sm2.get_original_prompt() == "fix bugs"
