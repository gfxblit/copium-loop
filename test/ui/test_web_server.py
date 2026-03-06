from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from copium_loop.telemetry import Telemetry
from copium_loop.ui.web_server import app, set_auth_token, set_telemetry


@pytest.fixture
def temp_log_dir(tmp_path):
    log_dir = tmp_path / ".copium" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


@pytest.fixture
def telemetry_with_temp_dir(temp_log_dir, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: temp_log_dir.parent.parent)
    return Telemetry("test_web_session")


@pytest.mark.asyncio
async def test_get_status():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get("/api/status")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_logs(telemetry_with_temp_dir):
    set_telemetry(telemetry_with_temp_dir)
    set_auth_token("test_token")
    telemetry_with_temp_dir.log_status("coder", "active")

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            response = await client.get(
                "/api/logs", headers={"X-Auth-Token": "test_token"}
            )
            assert response.status_code == 200
            logs = response.json()
            assert len(logs) >= 1
            assert logs[0]["node"] == "coder"
    finally:
        set_auth_token(None)
