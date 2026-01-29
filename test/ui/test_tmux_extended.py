import os
import subprocess
from unittest.mock import patch
from copium_loop.ui.tmux import switch_to_tmux_session

def test_switch_to_tmux_session_no_tmux_env():
    """Test that switch_to_tmux_session returns early if TMUX env is not set."""
    with patch.dict(os.environ, {}, clear=True):
        # This should return None and not call subprocess.run
        with patch("subprocess.run") as mock_run:
            switch_to_tmux_session("my-session")
            mock_run.assert_not_called()

def test_switch_to_tmux_session_called_process_error():
    """Test that switch_to_tmux_session handles subprocess.CalledProcessError."""
    with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,123,0"}):
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, ["tmux"])):
            # This should not raise an exception
            switch_to_tmux_session("non-existent-session")

def test_switch_to_tmux_session_unexpected_error(capsys):
    """Test that switch_to_tmux_session handles unexpected exceptions."""
    with patch.dict(os.environ, {"TMUX": "/tmp/tmux-1000/default,123,0"}):
        with patch("subprocess.run", side_effect=Exception("kaboom")):
            switch_to_tmux_session("my-session")
            captured = capsys.readouterr()
            assert "Unexpected error switching to tmux session 'my-session': kaboom" in captured.err
