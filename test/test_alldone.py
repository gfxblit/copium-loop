import unittest
from pathlib import Path
from unittest.mock import patch

from copium_loop.alldone import run_alldone


class TestAlldone(unittest.IsolatedAsyncioTestCase):
    @patch("copium_loop.alldone.is_git_repo")
    @patch("builtins.print")
    async def test_not_in_git_repo(self, mock_print, mock_is_git_repo):
        mock_is_git_repo.return_value = False
        code = await run_alldone()
        self.assertEqual(code, 1)
        mock_print.assert_called_with("Error: Not inside a git repository.")

    @patch("copium_loop.alldone.is_git_repo")
    @patch("copium_loop.alldone.is_dirty")
    @patch("builtins.print")
    async def test_dirty_repo(self, mock_print, mock_is_dirty, mock_is_git_repo):
        mock_is_git_repo.return_value = True
        mock_is_dirty.return_value = True
        code = await run_alldone()
        self.assertEqual(code, 1)
        mock_print.assert_called_with(
            "Error: Git repository has uncommitted or untracked files. Aborting."
        )

    @patch("copium_loop.alldone.is_git_repo")
    @patch("copium_loop.alldone.is_dirty")
    @patch("copium_loop.alldone.run_command", autospec=True)
    @patch("copium_loop.alldone.get_current_branch")
    @patch("copium_loop.alldone.get_repo_name")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.exists")
    @patch("os.chdir")
    @patch("builtins.print")
    @patch("pathlib.Path.home")
    async def test_unsafe_workspace(
        self,
        mock_home,
        mock_print,
        mock_chdir,
        mock_exists,
        mock_unlink,
        mock_rmtree,
        mock_get_repo_name,
        mock_get_current_branch,
        mock_run_command,
        mock_is_dirty,
        mock_is_git_repo,
    ):
        mock_home.return_value = Path("/home/user")
        mock_is_git_repo.return_value = True
        mock_is_dirty.return_value = False

        async def mock_run_cmd(cmd, args, **_kwargs):
            if cmd == "git" and args == ["rev-parse", "--show-toplevel"]:
                return {"exit_code": 0, "output": "/home/user/myproject\n"}
            return {"exit_code": 0, "output": ""}

        mock_run_command.side_effect = mock_run_cmd
        mock_get_current_branch.return_value = "feature-branch"
        mock_get_repo_name.return_value = "user/myproject"
        mock_exists.return_value = True

        code = await run_alldone()

        self.assertEqual(code, 1)
        mock_print.assert_called_with(
            "Error: Repository root '/home/user/myproject' is not a safe temporary workspace. Aborting."
        )
        # Safety check happens BEFORE unlinking now
        self.assertEqual(mock_unlink.call_count, 0)
        mock_chdir.assert_not_called()
        mock_rmtree.assert_not_called()

    @patch("copium_loop.alldone.is_git_repo")
    @patch("copium_loop.alldone.is_dirty")
    @patch("copium_loop.alldone.run_command", autospec=True)
    @patch("copium_loop.alldone.get_current_branch")
    @patch("copium_loop.alldone.get_repo_name")
    @patch("shutil.rmtree")
    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.exists")
    @patch("os.chdir")
    @patch("builtins.print")
    @patch("pathlib.Path.home")
    async def test_successful_alldone(
        self,
        mock_home,
        mock_print,
        mock_chdir,
        mock_exists,
        mock_unlink,
        mock_rmtree,
        mock_get_repo_name,
        mock_get_current_branch,
        mock_run_command,
        mock_is_dirty,
        mock_is_git_repo,
    ):
        mock_home.return_value = Path("/home/user")
        mock_is_git_repo.return_value = True
        mock_is_dirty.return_value = False

        async def mock_run_cmd(cmd, args, **_kwargs):
            if cmd == "git" and args == ["rev-parse", "--show-toplevel"]:
                return {
                    "exit_code": 0,
                    "output": "/home/user/.copium/workspaces/repo\n",
                }
            return {"exit_code": 0, "output": ""}

        mock_run_command.side_effect = mock_run_cmd
        mock_get_current_branch.return_value = "feature-branch"
        mock_get_repo_name.return_value = "user/repo"

        # Assume files exist
        mock_exists.return_value = True

        code = await run_alldone()

        self.assertEqual(code, 0)
        self.assertEqual(mock_unlink.call_count, 2)

        # Check tmux was killed
        mock_run_command.assert_any_call(
            "tmux",
            ["kill-session", "-t", "feature-branch"],
            capture_stderr=False,
        )

        # Check directory change and removal
        mock_chdir.assert_called_with("/home/user/.copium/workspaces")
        mock_rmtree.assert_called_with("/home/user/.copium/workspaces/repo")
        mock_print.assert_any_call(
            "Successfully cleaned up copium-loop workspace for 'feature-branch' in 'user/repo'."
        )
