import unittest
from pathlib import Path
from unittest.mock import patch

from copium_loop.alldone import AllDoneCommand


class TestIssue301Repro(unittest.IsolatedAsyncioTestCase):
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
    async def test_alldone_safety_check_path(
        self,
        mock_print,
        _mock_chdir,
        _mock_exists,
        _mock_unlink,
        mock_rmtree,
        _mock_get_repo_name,
        _mock_get_current_branch,
        mock_run_command,
        _mock_is_dirty,
        _mock_is_git_repo,
    ):
        """Test that alldone only deletes if in ~/.copium/workspaces/."""
        _mock_is_git_repo.return_value = True
        _mock_is_dirty.return_value = False
        _mock_get_current_branch.return_value = "feat"
        _mock_get_repo_name.return_value = "repo"

        # CASE 1: Path contains .copium but is NOT in ~/.copium/workspaces/
        # Current implementation would wrongly allow this.
        unsafe_path = "/tmp/some.copium/repo"

        async def mock_run_cmd(cmd, args, **_kwargs):
            if cmd == "git" and args == ["rev-parse", "--show-toplevel"]:
                return {"exit_code": 0, "output": unsafe_path + "\n"}
            return {"exit_code": 0, "output": ""}

        mock_run_command.side_effect = mock_run_cmd

        log_dir = Path("/home/user/.copium/logs")
        session_dir = Path("/home/user/.copium/sessions")
        cmd = AllDoneCommand(log_dir, session_dir)

        # Mock Path.home() to return /home/user
        with patch("pathlib.Path.home", return_value=Path("/home/user")):
            code = await cmd.execute()

        self.assertEqual(code, 1)
        mock_print.assert_any_call(
            f"Error: Repository root '{unsafe_path}' is not a safe temporary workspace. Aborting."
        )
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
    async def test_alldone_no_unlink_on_safety_failure(
        self,
        _mock_print,
        _mock_chdir,
        _mock_exists,
        mock_unlink,
        _mock_rmtree,
        _mock_get_repo_name,
        _mock_get_current_branch,
        mock_run_command,
        _mock_is_dirty,
        _mock_is_git_repo,
    ):
        """Test that alldone doesn't unlink files if the safety check fails."""
        _mock_is_git_repo.return_value = True
        _mock_is_dirty.return_value = False
        _mock_get_current_branch.return_value = "feat"
        _mock_get_repo_name.return_value = "repo"
        _mock_exists.return_value = True  # Files exist

        unsafe_path = "/home/user/my-legit-project"

        async def mock_run_cmd(cmd, args, **_kwargs):
            if cmd == "git" and args == ["rev-parse", "--show-toplevel"]:
                return {"exit_code": 0, "output": unsafe_path + "\n"}
            return {"exit_code": 0, "output": ""}

        mock_run_command.side_effect = mock_run_cmd

        log_dir = Path("/home/user/.copium/logs")
        session_dir = Path("/home/user/.copium/sessions")
        cmd = AllDoneCommand(log_dir, session_dir)

        with patch("pathlib.Path.home", return_value=Path("/home/user")):
            code = await cmd.execute()

        self.assertEqual(code, 1)
        mock_unlink.assert_not_called()


if __name__ == "__main__":
    unittest.main()
