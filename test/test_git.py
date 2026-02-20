import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from copium_loop import git
from copium_loop.copium_loop import WorkflowManager
from copium_loop.git import get_repo_name


@pytest.fixture
def mock_session_manager():
    """Mock SessionManager to prevent filesystem access."""
    with (
        patch("copium_loop.copium_loop.SessionManager"),
        patch("copium_loop.session_manager.SessionManager"),
    ):
        yield


@pytest.mark.asyncio
async def test_get_current_branch():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"output": "main\n", "exit_code": 0}
        branch = await git.get_current_branch()
        assert branch == "main"
        mock_run.assert_called_with(
            "git", ["branch", "--show-current"], node=None, capture_stderr=False
        )


@pytest.mark.asyncio
async def test_get_diff():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"output": "diff content", "exit_code": 0}
        diff = await git.get_diff("HEAD~1", "HEAD")
        assert diff == "diff content"
        mock_run.assert_called_with("git", ["diff", "HEAD~1", "HEAD"], node=None)


@pytest.mark.asyncio
async def test_is_dirty():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"output": "M file.py\n", "exit_code": 0}
        assert await git.is_dirty() is True
        mock_run.assert_called_with("git", ["status", "--porcelain"], node=None)

        mock_run.return_value = {"output": "", "exit_code": 0}
        assert await git.is_dirty() is False


@pytest.mark.asyncio
async def test_get_head():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"output": "abc123\n", "exit_code": 0}
        head = await git.get_head()
        assert head == "abc123"
        mock_run.assert_called_with(
            "git", ["rev-parse", "HEAD"], node=None, capture_stderr=False
        )


@pytest.mark.asyncio
async def test_fetch():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}
        await git.fetch()
        mock_run.assert_called_with("git", ["fetch", "origin"], node=None)


@pytest.mark.asyncio
async def test_rebase():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}
        await git.rebase("origin/main")
        mock_run.assert_called_with("git", ["rebase", "origin/main"], node=None)


@pytest.mark.asyncio
async def test_rebase_abort():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}
        await git.rebase_abort()
        mock_run.assert_called_with("git", ["rebase", "--abort"], node=None)


@pytest.mark.asyncio
async def test_push():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0}

        # Test default push
        await git.push()
        mock_run.assert_called_with("git", ["push", "origin"], node=None)

        # Test force push
        await git.push(force=True)
        mock_run.assert_called_with("git", ["push", "--force", "origin"], node=None)

        # Test push specific branch
        await git.push(branch="my-branch")
        mock_run.assert_called_with(
            "git", ["push", "-u", "origin", "my-branch"], node=None
        )


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_git_repo")
async def test_diff_uncommitted():
    """Test that get_diff captures uncommitted changes when head is None."""
    # Create a file and commit it
    with open("test.txt", "w") as f:
        f.write("initial content")
    subprocess.run(["git", "add", "test.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "initial commit", "-q"], check=True)

    # Get base commit hash
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    base_commit = result.stdout.strip()

    # Modify the file (uncommitted change)
    with open("test.txt", "w") as f:
        f.write("modified content")

    # Test get_diff with head=None (should capture uncommitted changes)
    diff = await git.get_diff(base_commit, head=None)
    assert "modified content" in diff
    assert "initial content" in diff


@pytest.mark.asyncio
@pytest.mark.usefixtures("temp_git_repo")
async def test_diff_committed():
    """Test that get_diff captures changes between two commits."""
    # Create a file and commit it
    with open("test.txt", "w") as f:
        f.write("initial content")
    subprocess.run(["git", "add", "test.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "initial commit", "-q"], check=True)

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    base_commit = result.stdout.strip()

    # Modify and commit
    with open("test.txt", "w") as f:
        f.write("modified content")
    subprocess.run(["git", "add", "test.txt"], check=True)
    subprocess.run(["git", "commit", "-m", "second commit", "-q"], check=True)

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    )
    head_commit = result.stdout.strip()

    # Test get_diff with explicit head
    diff = await git.get_diff(base_commit, head=head_commit)

    assert "modified content" in diff
    assert "initial content" in diff


@pytest.mark.asyncio
async def test_get_repo_name_parsing():
    urls = [
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("https://github.com/owner/repo", "owner/repo"),
        ("git@github.com:owner/repo", "owner/repo"),
        ("https://github.com/owner/repo/", "owner/repo"),
        ("https://github.com/user/my.project.git", "user/my.project"),
        ("git@github.com:user/my.project.git", "user/my.project"),
    ]

    for url, expected in urls:
        with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
            mock_run.side_effect = [
                {"exit_code": 0, "output": "origin\n"},
                {"exit_code": 0, "output": url + "\n"},
            ]
            repo = await get_repo_name()
            assert repo == expected


@pytest.mark.asyncio
async def test_get_repo_name_no_remote():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 0, "output": ""}
        with pytest.raises(ValueError, match="Could not determine git remote URL"):
            await get_repo_name()


@pytest.mark.asyncio
async def test_get_repo_name_unsupported_url():
    with patch("copium_loop.git.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = [
            {"exit_code": 0, "output": "origin\n"},
            {"exit_code": 0, "output": "https://example.com/not-a-repo\n"},
        ]
        with pytest.raises(
            ValueError, match="Could not parse repo name from remote URL"
        ):
            await get_repo_name()


@pytest.mark.asyncio
@pytest.mark.usefixtures("mock_session_manager")
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
@pytest.mark.usefixtures("mock_session_manager")
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
@pytest.mark.usefixtures("mock_session_manager")
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
@pytest.mark.usefixtures("mock_session_manager")
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
@pytest.mark.usefixtures("mock_session_manager")
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
@pytest.mark.usefixtures(
    "temp_git_repo",
    "mock_verify_environment",
    "mock_create_graph",
    "mock_session_manager",
)
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
