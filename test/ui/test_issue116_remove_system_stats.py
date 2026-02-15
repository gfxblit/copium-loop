import pytest
from textual.widgets import Static
from copium_loop.ui.textual_dashboard import TextualDashboard
from copium_loop.ui.footer_stats import CodexStatsStrategy

@pytest.mark.asyncio
async def test_system_stats_strategy_removed_from_dashboard(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    
    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    
    # Check that only CodexStatsStrategy is in stats_strategies
    strategies = [type(s) for s in app.stats_strategies]
    assert len(strategies) == 1
    assert strategies[0] == CodexStatsStrategy

@pytest.mark.asyncio
async def test_footer_does_not_contain_cpu_mem(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    
    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test() as pilot:
        await app.update_footer_stats()
        await pilot.pause()

        stats_bar = app.query_one("#stats-bar", Static)
        renderable = stats_bar.render()
        content = renderable.plain if hasattr(renderable, "plain") else str(renderable)
        assert "CPU:" not in content
        assert "MEM:" not in content
