import json
from unittest.mock import MagicMock, patch

import pytest

from copium_loop.ui.codexbar import CodexbarClient


class TestCodexbarClient:
    @pytest.fixture
    def mock_subprocess(self):
        with patch("subprocess.run") as mock:
            yield mock

    @pytest.fixture
    def client(self):
        return CodexbarClient()

    def test_get_usage_success(self, client, mock_subprocess):
        # Mock successful JSON output
        mock_output = json.dumps({"pro": 85, "flash": 40, "reset": "18:30"})

        mock_subprocess.return_value = MagicMock(stdout=mock_output, returncode=0)

        # Simulate that codexbar is found (we might need to mock shutil.which or checks in the client)
        with patch("shutil.which", return_value="/usr/local/bin/codexbar"):
            data = client.get_usage()

        assert data is not None
        assert data["pro"] == 85
        assert data["flash"] == 40
        assert data["reset"] == "18:30"

        # Verify the command called
        mock_subprocess.assert_called_with(
            ["/usr/local/bin/codexbar", "--format", "json"],
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )

    def test_get_usage_not_installed(self, client, mock_subprocess):
        with patch("shutil.which", return_value=None):
            data = client.get_usage()
            assert data is None

        # Should not call subprocess if not installed
        mock_subprocess.assert_not_called()

    def test_get_usage_command_fail(self, client, mock_subprocess):
        # Mock failure return code
        mock_subprocess.return_value = MagicMock(
            stdout="", stderr="Error", returncode=1
        )

        with patch("shutil.which", return_value="/usr/local/bin/codexbar"):
            data = client.get_usage()

        assert data is None

    def test_get_usage_json_error(self, client, mock_subprocess):
        # Mock invalid JSON
        mock_subprocess.return_value = MagicMock(stdout="Not JSON", returncode=0)

        with patch("shutil.which", return_value="/usr/local/bin/codexbar"):
            data = client.get_usage()

        assert data is None

    def test_caching(self, client, mock_subprocess):
        mock_output = json.dumps({"pro": 50, "flash": 20, "reset": "12:00"})
        mock_subprocess.return_value = MagicMock(stdout=mock_output, returncode=0)

        with patch("shutil.which", return_value="/usr/local/bin/codexbar"):
            # First call
            data1 = client.get_usage()
            assert data1["pro"] == 50

            # Second call immediately - should use cache
            data2 = client.get_usage()
            assert data2["pro"] == 50

            # Subprocess should have been called only once
            assert mock_subprocess.call_count == 1

            # Manually expire cache (if we can, or mock time)
            client._last_check = 0

            # Third call - should fetch again
            client.get_usage()
            assert mock_subprocess.call_count == 2
