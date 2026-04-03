import os
import unittest
from unittest.mock import patch

from copium_loop.alldone import run_alldone


class TestAlldone(unittest.IsolatedAsyncioTestCase):
    @patch("copium_loop.alldone.is_git_repo")
    @patch("builtins.print")
    async def test_not_in_git_repo(self, mock_print, mock_is_git_repo):
        mock_is_git_repo.return_value = False
        with self.assertRaises(SystemExit) as cm:
            await run_alldone()
        self.assertEqual(cm.exception.code, 1)
        mock_print.assert_called_with("Error: Not inside a git repository.")

    @patch("copium_loop.alldone.is_git_repo")
    @patch("copium_loop.alldone.is_dirty")
    @patch("builtins.print")
    async def test_dirty_repo(self, mock_print, mock_is_dirty, mock_is_git_repo):
        mock_is_git_repo.return_value = True
        mock_is_dirty.return_value = True
        with self.assertRaises(SystemExit) as cm:
            await run_alldone()
        self.assertEqual(cm.exception.code, 1)
        mock_print.assert_called_with(
            "Error: Git repository has uncommitted or untracked files. Aborting."
        )

    @patch("copium_loop.alldone.is_git_repo")
    @patch("copium_loop.alldone.is_dirty")
    @patch("copium_loop.alldone.run_command")
    @patch("copium_loop.alldone.get_current_branch")
    @patch("copium_loop.alldone.get_repo_name")
    @patch("os.chdir")
    @patch("shutil.rmtree")
    @patch("os.remove")
    @patch("os.path.exists")
    @patch("builtins.print")
    async def test_successful_alldone(
        self,
        mock_print,
        mock_exists,
        mock_remove,
        mock_rmtree,
        mock_chdir,
        mock_get_repo_name,
        mock_get_current_branch,
        mock_run_command,
        mock_is_dirty,
        mock_is_git_repo,
    ):
        mock_is_git_repo.return_value = True
        mock_is_dirty.return_value = False

        async def mock_run_cmd(cmd, args, **_kwargs):
            if cmd == "git" and args == ["rev-parse", "--show-toplevel"]:
                return {"exit_code": 0, "output": "/path/to/repo\n"}
            return {"exit_code": 0, "output": ""}

        mock_run_command.side_effect = mock_run_cmd
        mock_get_current_branch.return_value = "feature-branch"
        mock_get_repo_name.return_value = "user/repo"

        # Assume files exist
        mock_exists.return_value = True

        await run_alldone()

        # Check that files were removed
        expected_log_path = os.path.expanduser(
            "~/.copium/logs/user/repo/feature-branch.jsonl"
        )
        expected_session_path = os.path.expanduser(
            "~/.copium/sessions/user/repo/feature-branch.json"
        )
        mock_remove.assert_any_call(expected_log_path)
        mock_remove.assert_any_call(expected_session_path)

        # Check tmux was killed
        mock_run_command.assert_any_call(
            "tmux",
            ["kill-session", "-t", "feature-branch"],
            capture_stderr=False,
            check=False,
        )

        # Check directory change and removal
        mock_chdir.assert_called_with("..")
        mock_rmtree.assert_called_with("/path/to/repo")
        mock_print.assert_any_call(
            "Successfully cleaned up copium-loop workspace for 'feature-branch' in 'user/repo'."
        )


if __name__ == "__main__":
    unittest.main()
