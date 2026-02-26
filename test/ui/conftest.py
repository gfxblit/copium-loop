from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_gemini_stats_client():
    with patch("copium_loop.ui.textual_dashboard.GeminiStatsClient") as MockClient:
        instance = MockClient.return_value
        instance.get_usage.return_value = {
            "pro": 0,
            "flash": 0,
            "reset_pro": "never",
            "reset_flash": "never",
        }
        instance.get_usage_async = AsyncMock(
            return_value={
                "pro": 0,
                "flash": 0,
                "reset_pro": "never",
                "reset_flash": "never",
            }
        )
        yield MockClient
