import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.copium_loop import WorkflowManager


@pytest.fixture(autouse=True)
def mock_session_manager():
    """Mock SessionManager to prevent filesystem access."""
    with (
        patch("copium_loop.copium_loop.SessionManager"),
        patch("copium_loop.session_manager.SessionManager"),
    ):
        yield


@pytest.mark.asyncio
async def test_initial_commit_hash_for_architect_with_origin_main(
    mock_verify_environment,
    mock_create_graph,
    mock_get_head,
):
    """
    Test that when start_node is 'architect', the initial_commit_hash
    is set to 'origin/main' if it exists.
    """
    mock_verify_environment.return_value = True
    mock_get_head.return_value = "head_hash"

    # Mock resolve_ref (we'll add this to git.py)
    with patch(
        "copium_loop.copium_loop.is_git_repo", new_callable=AsyncMock
    ) as mock_is_git:
        mock_is_git.return_value = True

        # Let's assume we'll use a new function in git.py called resolve_ref
        with patch(
            "copium_loop.copium_loop.resolve_ref", new_callable=AsyncMock
        ) as mock_resolve_ref:
            mock_resolve_ref.return_value = "origin_main_hash"

            manager = WorkflowManager(start_node="architect")
            mock_graph = AsyncMock()
            mock_graph.ainvoke.return_value = {"status": "completed"}
            mock_create_graph.return_value = mock_graph

            await manager.run("test prompt")

            # Verify initial state
            state = mock_graph.ainvoke.call_args[0][0]
            assert state["initial_commit_hash"] == "origin_main_hash"
            mock_resolve_ref.assert_called_with(ref="origin/main", node="architect")


@pytest.mark.asyncio
async def test_initial_commit_hash_for_architect_fallback_to_main(
    mock_verify_environment,
    mock_create_graph,
    mock_get_head,
):
    """
    Test that when start_node is 'architect', the initial_commit_hash
    falls back to 'main' if 'origin/main' does not exist.
    """
    mock_verify_environment.return_value = True
    mock_get_head.return_value = "head_hash"

    with patch(
        "copium_loop.copium_loop.is_git_repo", new_callable=AsyncMock
    ) as mock_is_git:
        mock_is_git.return_value = True
        with patch(
            "copium_loop.copium_loop.get_current_branch", new_callable=AsyncMock
        ) as mock_get_branch:
            mock_get_branch.return_value = "feature-branch"

            with patch(
                "copium_loop.copium_loop.resolve_ref", new_callable=AsyncMock
            ) as mock_resolve_ref:

                def side_effect(ref, node):  # noqa: ARG001
                    if ref == "main":
                        return "main_hash"
                    return None

                mock_resolve_ref.side_effect = side_effect

                manager = WorkflowManager(start_node="architect")
                mock_graph = AsyncMock()
                mock_graph.ainvoke.return_value = {"status": "completed"}
                mock_create_graph.return_value = mock_graph

                await manager.run("test prompt")

                # Verify initial state
                state = mock_graph.ainvoke.call_args[0][0]
                assert state["initial_commit_hash"] == "main_hash"
                # Should have tried origin/main then main
                assert mock_resolve_ref.call_count >= 2


@pytest.mark.asyncio
async def test_initial_commit_hash_for_architect_on_main(
    mock_verify_environment,
    mock_create_graph,
    mock_get_head,
):
    """
    Test that when start_node is 'architect' and we are on 'main',
    it skips 'main' and 'origin/main' as diff base.
    """
    mock_verify_environment.return_value = True
    mock_get_head.return_value = "head_hash"

    with patch(
        "copium_loop.copium_loop.is_git_repo", new_callable=AsyncMock
    ) as mock_is_git:
        mock_is_git.return_value = True
        with patch(
            "copium_loop.copium_loop.get_current_branch", new_callable=AsyncMock
        ) as mock_get_branch:
            mock_get_branch.return_value = "main"

            with patch(
                "copium_loop.copium_loop.resolve_ref", new_callable=AsyncMock
            ) as mock_resolve_ref:

                def side_effect(ref, node):  # noqa: ARG001
                    # Should NOT be called for 'main' or 'origin/main'
                    if ref in ["main", "origin/main"]:
                        pytest.fail(f"Should not try to resolve {ref} when on main")
                    return None

                mock_resolve_ref.side_effect = side_effect

                manager = WorkflowManager(start_node="architect")
                mock_graph = AsyncMock()
                mock_graph.ainvoke.return_value = {"status": "completed"}
                mock_create_graph.return_value = mock_graph

                await manager.run("test prompt")

                # Verify initial state falls back to HEAD
                state = mock_graph.ainvoke.call_args[0][0]
                assert state["initial_commit_hash"] == "head_hash"


@pytest.mark.asyncio
async def test_initial_commit_hash_for_architect_fallback_to_head(
    mock_verify_environment,
    mock_create_graph,
    mock_get_head,
):
    """
    Test that when start_node is 'architect', the initial_commit_hash
    falls back to 'HEAD' if 'origin/main' does not exist.
    """
    mock_verify_environment.return_value = True
    mock_get_head.return_value = "head_hash"

    with patch(
        "copium_loop.copium_loop.is_git_repo", new_callable=AsyncMock
    ) as mock_is_git:
        mock_is_git.return_value = True

        with patch(
            "copium_loop.copium_loop.resolve_ref", new_callable=AsyncMock
        ) as mock_resolve_ref:
            mock_resolve_ref.return_value = None  # origin/main not found

            manager = WorkflowManager(start_node="architect")
            mock_graph = AsyncMock()
            mock_graph.ainvoke.return_value = {"status": "completed"}
            mock_create_graph.return_value = mock_graph

            await manager.run("test prompt")

            # Verify initial state
            state = mock_graph.ainvoke.call_args[0][0]
            assert state["initial_commit_hash"] == "head_hash"


@pytest.mark.asyncio
async def test_initial_commit_hash_for_coder_stays_head(
    mock_verify_environment,
    mock_create_graph,
    mock_get_head,
    mock_get_test_command,
    mock_run_command,
):
    """
    Test that when start_node is 'coder', the initial_commit_hash
    is set to 'HEAD' even if 'origin/main' exists.
    """
    mock_verify_environment.return_value = True
    mock_get_head.return_value = "head_hash"
    mock_get_test_command.return_value = ("pytest", [])
    mock_run_command.return_value = {"exit_code": 0, "output": ""}

    with patch(
        "copium_loop.copium_loop.is_git_repo", new_callable=AsyncMock
    ) as mock_is_git:
        mock_is_git.return_value = True

        with patch(
            "copium_loop.copium_loop.resolve_ref", new_callable=AsyncMock
        ) as mock_resolve_ref:
            mock_resolve_ref.return_value = "origin_main_hash"

            manager = WorkflowManager(start_node="coder")
            mock_graph = AsyncMock()
            mock_graph.ainvoke.return_value = {"status": "completed"}
            mock_create_graph.return_value = mock_graph

            await manager.run("test prompt")

            # Verify initial state
            state = mock_graph.ainvoke.call_args[0][0]
            assert state["initial_commit_hash"] == "head_hash"
            # resolve_ref should NOT be called for coder
            mock_resolve_ref.assert_not_called()


@pytest.mark.asyncio
async def test_integration_architect_diff_base(
    temp_git_repo, mock_verify_environment, mock_create_graph
):
    """
    Integration test: verify that WorkflowManager correctly identifies origin/main
    in a real git repository.
    """
    assert temp_git_repo.exists()
    mock_verify_environment.return_value = True

    # Setup: Create initial commit on main
    with open("README.md", "w") as f:
        f.write("Initial content")
    subprocess.run(["git", "add", "README.md"], check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)

    main_hash = subprocess.check_output(["git", "rev-parse", "main"]).decode().strip()

    # Simulate origin/main by creating a remote-tracking branch
    # In a real scenario, this would be there after a fetch.
    # We can just create the ref manually for testing purposes.
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/main", "main"], check=True
    )

    # Create feature branch and add a commit
    subprocess.run(["git", "checkout", "-b", "feature"], check=True)
    with open("feature.txt", "w") as f:
        f.write("Feature content")
    subprocess.run(["git", "add", "feature.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "Feature commit"], check=True)

    feature_hash = (
        subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    )

    assert main_hash != feature_hash

    # Run workflow starting at architect
    manager = WorkflowManager(start_node="architect")
    mock_graph = AsyncMock()
    mock_graph.ainvoke.return_value = {"status": "completed"}
    mock_create_graph.return_value = mock_graph

    await manager.run("test prompt")

    # Verify initial state uses main_hash (from origin/main)
    state = mock_graph.ainvoke.call_args[0][0]
    assert state["initial_commit_hash"] == main_hash
    assert state["initial_commit_hash"] != feature_hash
