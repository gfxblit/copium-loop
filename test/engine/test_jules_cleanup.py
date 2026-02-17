from unittest.mock import MagicMock, patch

import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_jules_engine_cleans_up_stale_output():
    """Verify that JulesEngine cleans up stale JULES_OUTPUT.txt before running."""
    engine = JulesEngine()

    with (
        patch("copium_loop.engine.jules.run_command") as mock_run,
        patch("copium_loop.engine.jules.stream_subprocess") as mock_stream,
        patch("os.path.exists") as mock_exists,
        patch("os.remove") as mock_remove,
        patch("builtins.open", MagicMock()) as mock_file_open,
    ):
        # Setup mocks for successful run
        mock_run.side_effect = [
            {"exit_code": 0, "output": "origin\n"},
            {"exit_code": 0, "output": "https://github.com/owner/repo.git\n"},
        ]
        mock_stream.side_effect = [
            ("Session ID: sess_123\n", 0, False, None),
            ("Status: Completed\n", 0, False, None),
            ("Pulled changes\n", 0, False, None),
        ]

        # Simulate JULES_OUTPUT.txt existing before run
        mock_exists.return_value = True

        mock_file_open.return_value.__enter__.return_value.read.return_value = (
            "New Result"
        )

        await engine.invoke("Test prompt")

        # Verify os.remove was called
        # We expect at least one call to remove "JULES_OUTPUT.txt"
        mock_remove.assert_called_with("JULES_OUTPUT.txt")


@pytest.mark.asyncio
async def test_jules_engine_cleans_up_after_run():
    """Verify that JulesEngine cleans up JULES_OUTPUT.txt after running."""
    engine = JulesEngine()

    with (
        patch("copium_loop.engine.jules.run_command") as mock_run,
        patch("copium_loop.engine.jules.stream_subprocess") as mock_stream,
        patch("os.path.exists") as mock_exists,
        patch("os.remove") as mock_remove,
        patch("builtins.open", MagicMock()) as mock_file_open,
    ):
        # Setup mocks for successful run
        mock_run.side_effect = [
            {"exit_code": 0, "output": "origin\n"},
            {"exit_code": 0, "output": "https://github.com/owner/repo.git\n"},
        ]
        mock_stream.side_effect = [
            ("Session ID: sess_123\n", 0, False, None),
            ("Status: Completed\n", 0, False, None),
            ("Pulled changes\n", 0, False, None),
        ]

        # Simulate JULES_OUTPUT.txt existing during read
        mock_exists.return_value = True
        mock_file_open.return_value.__enter__.return_value.read.return_value = (
            "New Result"
        )

        await engine.invoke("Test prompt")

        # Verify os.remove was called twice: once before, once after
        assert mock_remove.call_count >= 2
        mock_remove.assert_any_call("JULES_OUTPUT.txt")
