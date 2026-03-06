import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from copium_loop.ui.web_server import app, set_telemetry
from copium_loop.telemetry import Telemetry
from pathlib import Path

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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/status")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_get_logs(telemetry_with_temp_dir):
    set_telemetry(telemetry_with_temp_dir)
    telemetry_with_temp_dir.log_status("coder", "active")
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get("/api/logs")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) >= 1
        assert logs[0]["node"] == "coder"
