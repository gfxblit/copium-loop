from unittest.mock import MagicMock, patch

import pytest

from copium_loop.engine.jules import JulesEngine


@pytest.mark.asyncio
async def test_jules_engine_invoke_with_models_keyword():
    """
    Test that JulesEngine.invoke accepts 'models' as a keyword argument,
    matching the LLMEngine base class signature.
    """
    with (
        patch("copium_loop.engine.jules.run_command") as mock_run,
        patch("copium_loop.engine.jules.stream_subprocess") as mock_stream,
        patch("builtins.open", MagicMock()) as mock_file_open,
        patch("os.path.exists", return_value=True),
        patch("asyncio.sleep", return_value=None),
    ):
        # Mock git remote detection
        mock_run.side_effect = [
            {"exit_code": 0, "output": "origin\n"},
            {"exit_code": 0, "output": "https://github.com/owner/repo.git\n"},
        ]

        # Mock jules remote lifecycle
        mock_stream.side_effect = [
            ("Session ID: sess_123\n", 0, False, None),  # jules remote new
            ("Status: Completed\n", 0, False, None),  # jules remote list
            ("Pulled changes\n", 0, False, None),  # jules remote pull
        ]

        mock_file_open.return_value.__enter__.return_value.read.return_value = "Success"

        engine = JulesEngine()
        # This should NOT raise TypeError: JulesEngine.invoke() got an unexpected keyword argument 'models'
        result = await engine.invoke(
            "Test prompt", models=["gpt-4o", "claude-3-5-sonnet"], node="test_node"
        )

        assert result == "Success"
