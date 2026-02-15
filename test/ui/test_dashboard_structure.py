import pytest
from textual.widgets import Footer, Header

from copium_loop.ui.textual_dashboard import TextualDashboard


@pytest.mark.asyncio
async def test_dashboard_structure(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    app = TextualDashboard(log_dir=log_dir, enable_polling=False)
    async with app.run_test():
        assert app.query_one(Header)
        assert app.query_one(Footer)
