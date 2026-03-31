from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copium_loop.workon import (
    check_dependencies,
    find_remote_url,
    resolve_branch_name,
    slugify,
    workon_main,
)


@pytest.mark.asyncio
async def test_check_dependencies_missing():
    with patch("shutil.which") as mock_which:
        # Mock gh and tmux missing, git found, pnpm found
        mock_which.side_effect = lambda tool: {
            "gh": None,
            "tmux": None,
            "git": "/usr/bin/git",
            "pnpm": "/usr/local/bin/pnpm",
        }.get(tool)

        with pytest.raises(SystemExit) as e:
            await check_dependencies()
        assert e.value.code == 1


def test_slugify():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("Fix: some bug #123") == "fix-some-bug-123"
    assert slugify("  Extra   Spaces  ") == "extra-spaces"
    assert slugify("Special characters !@#$%^&*()") == "special-characters"


@pytest.mark.asyncio
async def test_resolve_branch_name_from_url():
    with patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run:
        # Mock gh issue view output as JSON
        mock_run.return_value = {
            "exit_code": 0,
            "output": '{"title": "My Awesome Feature", "number": 456}',
        }

        url = "https://github.com/owner/repo/issues/456"
        branch_name = await resolve_branch_name(url)

        assert branch_name == "my-awesome-feature-issue456"


@pytest.mark.asyncio
async def test_resolve_branch_name_gh_text_fallback():
    with patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run:
        # Mock gh issue view output as plain text
        mock_run.return_value = {
            "exit_code": 0,
            "output": "title:\tPlain Text Title\nnumber:\t789\n",
        }

        url = "https://github.com/owner/repo/issues/789"
        branch_name = await resolve_branch_name(url)
        assert branch_name == "plain-text-title-issue789"


@pytest.mark.asyncio
async def test_resolve_branch_name_malicious_input():
    with patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = {"exit_code": 1, "output": "error"}

        # Input that looks like an option
        malicious_input = "https://github.com/--help"
        await resolve_branch_name(malicious_input)

        # Verify it was called with -- to separate options from arguments
        # Find the call to gh issue view
        gh_call = next(c for c in mock_run.call_args_list if c.args[0] == "gh")
        assert "--" in gh_call.args[1]
        assert malicious_input in gh_call.args[1]
        # Ensure -- comes before malicious_input
        idx_dashdash = gh_call.args[1].index("--")
        idx_input = gh_call.args[1].index(malicious_input)
        assert idx_dashdash < idx_input


@pytest.mark.asyncio
async def test_find_remote_url_from_dotfile(tmp_path):
    # Setup .workon-remote file
    remote_file = tmp_path / ".workon-remote"
    remote_url = "git@github.com:owner/repo.git"
    remote_file.write_text(remote_url)

    with patch("os.getcwd", return_value=str(tmp_path)):
        url = await find_remote_url()
        assert url == remote_url


@pytest.mark.asyncio
async def test_find_remote_url_from_siblings(tmp_path):
    # Setup sibling directories
    repo_dir = tmp_path / "existing-repo"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    with (
        patch("os.getcwd", return_value=str(tmp_path)),
        patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run,
    ):
        mock_run.return_value = {
            "exit_code": 0,
            "output": "git@github.com:owner/repo.git\n",
        }

        url = await find_remote_url()
        assert url == "git@github.com:owner/repo.git"

        # Verify it checked the existing-repo
        mock_run.assert_called()
        args, _ = mock_run.call_args
        assert "remote" in args[1]
        assert "get-url" in args[1]


@pytest.mark.asyncio
async def test_workon_main_no_remote_error():
    args = MagicMock()
    args.issue = "some-issue"
    with (
        patch("copium_loop.workon.check_dependencies", new_callable=AsyncMock),
        patch("copium_loop.workon.resolve_branch_name", return_value="branch"),
        patch("copium_loop.workon.find_remote_url", return_value=None),
    ):
        with pytest.raises(SystemExit) as e:
            await workon_main(args)
        assert e.value.code == 1


@pytest.mark.asyncio
async def test_workon_main_clone_fallback(tmp_path):
    args = MagicMock()
    args.issue = "issue-1"
    with (
        patch("copium_loop.workon.check_dependencies", new_callable=AsyncMock),
        patch("copium_loop.workon.resolve_branch_name", return_value="branch-1"),
        patch("copium_loop.workon.find_remote_url", return_value="git@remote"),
        patch("os.getcwd", return_value=str(tmp_path)),
        patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run,
        patch("copium_loop.workon.TmuxManager"),
    ):
        # First clone fails (branch not found)
        # Second clone succeeds
        mock_run.side_effect = [
            {"exit_code": 1, "output": "branch not found"},
            {"exit_code": 0, "output": ""},
            {"exit_code": 0, "output": ""},
        ]
        await workon_main(args)
        assert mock_run.call_count == 3
        # Verify it tried to create the branch
        assert mock_run.call_args_list[2].args[1] == ["checkout", "-b", "branch-1"]


@pytest.mark.asyncio
async def test_workon_main_existing_workspace(tmp_path):
    args = MagicMock()
    args.issue = "issue-1"
    workspace = tmp_path / "branch-1"
    workspace.mkdir()

    with (
        patch("copium_loop.workon.check_dependencies", new_callable=AsyncMock),
        patch("copium_loop.workon.resolve_branch_name", return_value="branch-1"),
        patch("copium_loop.workon.find_remote_url", return_value="git@remote"),
        patch("os.getcwd", return_value=str(tmp_path)),
        patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run,
        patch("copium_loop.workon.TmuxManager"),
    ):
        mock_run.return_value = {"exit_code": 0, "output": ""}
        await workon_main(args)
        # Should call git checkout
        mock_run.assert_called_with(
            "git", ["checkout", "branch-1"], dir_path=str(workspace)
        )


@pytest.mark.asyncio
async def test_workon_main_attach_session():
    args = MagicMock()
    args.issue = "issue-1"
    with (
        patch("copium_loop.workon.check_dependencies", new_callable=AsyncMock),
        patch("copium_loop.workon.resolve_branch_name", return_value="branch-1"),
        patch("copium_loop.workon.find_remote_url", return_value="git@remote"),
        patch("os.path.exists", return_value=True),
        patch("copium_loop.workon.run_command", new_callable=AsyncMock),
        patch("copium_loop.workon.TmuxManager") as mock_tmux_cls,
    ):
        mock_tmux = mock_tmux_cls.return_value
        mock_tmux.has_session.return_value = True

        # Mock not in TMUX
        with patch.dict("os.environ", {}, clear=True):
            await workon_main(args)
            mock_tmux.attach_session.assert_called_with("branch-1")

        # Mock in TMUX
        with patch.dict("os.environ", {"TMUX": "/tmp/tmux"}):
            await workon_main(args)
            mock_tmux.switch_client.assert_called_with("branch-1")


@pytest.mark.asyncio
async def test_workon_main_full_flow(tmp_path):
    issue_url = "https://github.com/owner/repo/issues/123"
    branch_name = "my-feature-issue123"
    remote_url = "git@github.com:owner/repo.git"

    with (
        patch("copium_loop.workon.check_dependencies", new_callable=AsyncMock),
        patch(
            "copium_loop.workon.resolve_branch_name", return_value=branch_name
        ) as mock_resolve,
        patch(
            "copium_loop.workon.find_remote_url", return_value=remote_url
        ) as mock_find_remote,
        patch("os.getcwd", return_value=str(tmp_path)),
        patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run,
        patch("copium_loop.workon.TmuxManager") as mock_tmux_cls,
    ):
        mock_tmux = mock_tmux_cls.return_value
        mock_tmux.has_session.return_value = False

        mock_run.return_value = {"exit_code": 0, "output": ""}

        # Set args
        args = MagicMock()
        args.issue = issue_url

        await workon_main(args)

        # Verify steps
        mock_resolve.assert_called_with(issue_url)
        mock_find_remote.assert_called_once()

        # Verify clone was called
        clone_calls = [
            call for call in mock_run.call_args_list if "clone" in call.args[1]
        ]
        assert len(clone_calls) > 0
        assert remote_url in clone_calls[0].args[1]
        assert branch_name in clone_calls[0].args[1]

        # Verify tmux session creation
        mock_tmux.new_session.assert_called_once()
        assert mock_tmux.new_session.call_args[0][0] == branch_name

        # Verify bootstrap command
        mock_tmux.send_keys.assert_called()


@pytest.mark.asyncio
async def test_find_remote_url_from_issue_url():
    # Test that remote URL is inferred from GitHub issue URL
    issue_url = "https://github.com/gfxblit/copium-loop/issues/300"
    with (
        patch("os.path.exists", return_value=False),
        patch("os.listdir", return_value=[]),
    ):  # Ensure .workon-remote not found
        url = await find_remote_url(issue_url)
        assert url == "https://github.com/gfxblit/copium-loop.git"

    # Test repo name with dots
    issue_url = "https://github.com/some.owner/some.repo/issues/123"
    url = await find_remote_url(issue_url)
    assert url == "https://github.com/some.owner/some.repo.git"

    # Test repo URL directly
    repo_url = "https://github.com/gfxblit/copium-loop"
    url = await find_remote_url(repo_url)
    assert url == "https://github.com/gfxblit/copium-loop.git"

    # Test SSH URL
    ssh_url = "git@github.com:gfxblit/copium-loop.git"
    url = await find_remote_url(ssh_url)
    assert url == "git@github.com:gfxblit/copium-loop.git"


@pytest.mark.asyncio
async def test_pnpm_detection_only_lockfile(tmp_path):
    # If only package.json exists, it should NOT run pnpm install
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "package.json").write_text("{}")
    (
        workspace / ".git"
    ).mkdir()  # simulate it being a git repo so it doesn't try to clone

    args = MagicMock()
    args.issue = "issue"

    with (
        patch("copium_loop.workon.check_dependencies", new_callable=AsyncMock),
        patch("copium_loop.workon.resolve_branch_name", return_value="workspace"),
        patch("copium_loop.workon.find_remote_url", return_value="git@remote"),
        patch("os.getcwd", return_value=str(tmp_path)),
        patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run,
        patch("copium_loop.workon.TmuxManager"),
    ):
        mock_run.return_value = {"exit_code": 0, "output": ""}
        await workon_main(args)

        # Verify pnpm install was NOT called
        pnpm_calls = [
            call for call in mock_run.call_args_list if call.args[0] == "pnpm"
        ]
        assert len(pnpm_calls) == 0

    # If pnpm-lock.yaml exists, it SHOULD run pnpm install
    (workspace / "pnpm-lock.yaml").write_text("")
    with (
        patch("copium_loop.workon.check_dependencies", new_callable=AsyncMock),
        patch("copium_loop.workon.resolve_branch_name", return_value="workspace"),
        patch("copium_loop.workon.find_remote_url", return_value="git@remote"),
        patch("os.getcwd", return_value=str(tmp_path)),
        patch("copium_loop.workon.run_command", new_callable=AsyncMock) as mock_run,
        patch("copium_loop.workon.TmuxManager"),
    ):
        mock_run.return_value = {"exit_code": 0, "output": ""}
        await workon_main(args)

        # Verify pnpm install WAS called
        pnpm_calls = [
            call for call in mock_run.call_args_list if call.args[0] == "pnpm"
        ]
        assert len(pnpm_calls) == 1
