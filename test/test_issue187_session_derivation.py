from unittest.mock import MagicMock, patch

import pytest

from copium_loop.telemetry import get_telemetry


@pytest.fixture(autouse=True)
def reset_telemetry():
    global _telemetry_instance
    _telemetry_instance = None
    yield
    _telemetry_instance = None


def test_session_id_derivation():
    """Verify session ID is derived from git repo and branch."""
    with patch("subprocess.run") as mock_run:

        def side_effect(cmd, **_kwargs):
            mock = MagicMock()
            mock.returncode = 0
            if "remote" in cmd and "get-url" in cmd:
                mock.stdout = "git@github.com:owner/repo.git\n"
            elif "branch" in cmd and "--show-current" in cmd:
                mock.stdout = "feature-branch\n"
            return mock

        mock_run.side_effect = side_effect

        telemetry = get_telemetry()
        assert telemetry.session_id == "owner-repo/feature-branch"


def test_session_id_fallback():
    """Verify session ID fallback when not in a git repo."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("not a git repo")

        with patch("time.time", return_value=1234567890):
            telemetry = get_telemetry()
            assert telemetry.session_id == "session_1234567890"
