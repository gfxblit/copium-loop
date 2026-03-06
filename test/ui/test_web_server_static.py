import os

import pytest
from httpx import ASGITransport, AsyncClient

from copium_loop.ui.web_server import app


@pytest.mark.asyncio
async def test_serve_index_html():
    # Only run if web/dist exists
    web_dist_dir = os.path.join(os.path.dirname(__file__), "..", "..", "web", "dist")
    if not os.path.exists(web_dist_dir):
        pytest.skip("web/dist not found")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "<html" in response.text.lower()
