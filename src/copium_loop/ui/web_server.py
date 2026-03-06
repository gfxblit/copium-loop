import asyncio
import contextlib
import os

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from copium_loop.telemetry import Telemetry

app = FastAPI()

_telemetry: Telemetry | None = None
_active_websockets: set[WebSocket] = set()
_loop: asyncio.AbstractEventLoop | None = None
_auth_token: str | None = None


def set_telemetry(telemetry: Telemetry):
    global _telemetry, _loop
    _telemetry = telemetry
    with contextlib.suppress(RuntimeError):
        _loop = asyncio.get_running_loop()


def set_auth_token(token: str):
    global _auth_token
    _auth_token = token


@app.get("/api/status")
def get_status():
    return {"status": "ok"}


@app.get("/api/logs")
def get_logs(x_auth_token: str = Header(None)):
    if _auth_token and x_auth_token != _auth_token:
        raise HTTPException(status_code=403, detail="Invalid auth token")
    
    if not _telemetry:
        return JSONResponse(
            content={"error": "Telemetry not initialized"}, status_code=500
        )
    return _telemetry.read_log()


@app.get("/api/graph")
def get_graph(x_auth_token: str = Header(None)):
    if _auth_token and x_auth_token != _auth_token:
        raise HTTPException(status_code=403, detail="Invalid auth token")

    # Nodes and canonical edges for visualization
    return {
        "nodes": [
            {"id": "coder", "label": "Coder"},
            {"id": "tester", "label": "Tester"},
            {"id": "architect", "label": "Architect"},
            {"id": "reviewer", "label": "Reviewer"},
            {"id": "pr_pre_checker", "label": "PR Pre-Checker"},
            {"id": "pr_creator", "label": "PR Creator"},
            {"id": "journaler", "label": "Journaler"},
        ],
        "edges": [
            {"source": "coder", "target": "tester"},
            {"source": "tester", "target": "architect"},
            {"source": "architect", "target": "reviewer"},
            {"source": "reviewer", "target": "pr_pre_checker"},
            {"source": "pr_pre_checker", "target": "pr_creator"},
            {"source": "tester", "target": "coder", "label": "fail"},
            {"source": "architect", "target": "coder", "label": "reject"},
            {"source": "reviewer", "target": "coder", "label": "reject"},
            {"source": "pr_creator", "target": "coder", "label": "fail"},
        ],
    }


@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(None)):
    if _auth_token and token != _auth_token:
        # For WebSockets, we can't easily return a 403, so we close the connection
        await websocket.close(code=1008)  # Policy Violation
        return

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
