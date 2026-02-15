import pytest
from rich.text import Text
from textual.css.scalar import Unit
from textual.widgets import Static

from copium_loop.ui.textual_dashboard import TextualDashboard


@pytest.mark.asyncio
async def test_stats_bar_height_auto(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test():
        stats_bar = app.query_one("#stats-bar", Static)

        # Currently it has height: auto in CSS
        assert stats_bar.styles.height.unit == Unit.AUTO


@pytest.mark.asyncio
async def test_stats_bar_wraps_with_long_content(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    app = TextualDashboard(log_dir=log_dir, enable_polling=False)

    async with app.run_test() as pilot:
        # Set a very narrow width to force wrapping
        await pilot.resize_terminal(40, 24)
        stats_bar = app.query_one("#stats-bar", Static)

        # Inject long content
        long_text = Text(" ".join(["LONG_CONTENT"] * 20))
        stats_bar.update(long_text)
        await pilot.pause()

        # If height is auto, it should be more than 2 when it wraps
        assert stats_bar.region.height > 2
