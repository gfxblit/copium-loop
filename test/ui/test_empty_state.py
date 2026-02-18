import pytest
from textual.widgets import Label

from copium_loop.ui.textual_dashboard import TextualDashboard


@pytest.mark.asyncio
async def test_textual_dashboard_empty_state(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        # Trigger update with empty logs
        await app.update_from_logs()
        await pilot.pause()

        # Check for the empty state label
        try:
            # Checking presence is enough as the content is hardcoded in the source
            app.query_one("#empty-state-label", Label)
        except Exception:
            pytest.fail(
                "Empty state label '#empty-state-label' not found when no sessions are present."
            )
