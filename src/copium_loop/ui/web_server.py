import asyncio
import contextlib
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from copium_loop.telemetry import Telemetry

app = FastAPI()

_telemetry: Telemetry | None = None
_active_websockets: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None


def set_telemetry(telemetry: Telemetry):
    global _telemetry, _loop
    _telemetry = telemetry
    with contextlib.suppress(RuntimeError):
        _loop = asyncio.get_running_loop()


@app.get("/api/status")
def get_status():
    return {"status": "ok"}


@app.get("/api/logs")
def get_logs():
    if not _telemetry:
        return JSONResponse(
            content={"error": "Telemetry not initialized"}, status_code=500
        )
    return _telemetry.read_log()


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _active_websockets.add(websocket)

    # Send initial state/logs upon connection
    if _telemetry:
        logs = _telemetry.read_log()
        await websocket.send_json({"event_type": "snapshot", "data": logs})

    try:
        while True:
            # We don't expect messages from client for now, but need to keep it open
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _active_websockets.discard(websocket)


def broadcast_telemetry_event(event: dict):
    """Broadcasts a telemetry event to all connected WebSockets."""
    if not _active_websockets or not _loop:
        return

    # This is called from the Telemetry thread, so we need to bridge to asyncio
    if _loop.is_running():
        for ws in list(_active_websockets):
            asyncio.run_coroutine_threadsafe(ws.send_json(event), _loop)


# Subscriber callback for Telemetry
def on_telemetry_event(event: dict):
    broadcast_telemetry_event(event)


# Attach subscriber when telemetry is set
def initialize_web_server(telemetry: Telemetry):
    set_telemetry(telemetry)
    telemetry.add_subscriber(on_telemetry_event)


# Serve static files if web/dist exists
web_dist_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "web", "dist")
if os.path.exists(web_dist_dir):
    app.mount("/", StaticFiles(directory=web_dist_dir, html=True), name="static")
else:
    # If not built, maybe serve from a dev location or just skip
    pass
