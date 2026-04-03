from unittest.mock import AsyncMock, patch

import pytest

from copium_loop.__main__ import async_main


@pytest.mark.asyncio
async def test_alldone_subcommand():
    with (
        patch("sys.argv", ["copium-loop", "alldone"]),
        patch(
            "copium_loop.alldone.run_alldone", new_callable=AsyncMock
        ) as mock_run_alldone,
        patch("sys.exit", side_effect=SystemExit(0)),
    ):
        with pytest.raises(SystemExit) as exc_info:
            await async_main()
        mock_run_alldone.assert_called_once()
        assert exc_info.value.code == 0
