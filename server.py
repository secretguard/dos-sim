import asyncio
import glob
import os
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from validator import run_test

app = FastAPI(title="ISP Scrubbing Validator")
app.mount("/static", StaticFiles(directory="static"), name="static")

_active_task: asyncio.Task = None
_stop_event: asyncio.Event = None
_clients: set[WebSocket] = set()


async def _broadcast(msg: dict):
    dead = set()
    for ws in _clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.add(ws)
    _clients.difference_update(dead)


def _validate_config(config: dict) -> str | None:
    required = [
        "target", "start_users", "ramp_step", "max_users",
        "stage_duration_s", "timeout_s", "cooldown_s",
    ]
    for field in required:
        if field not in config:
            return f"Missing field: {field}"

    if not str(config["target"]).startswith(("http://", "https://")):
        return "Target must start with http:// or https://"

    try:
        su = int(config["start_users"])
        mu = int(config["max_users"])
        rs = int(config["ramp_step"])
        if su < 1 or rs < 1 or mu < su:
            return "start_users >= 1, ramp_step >= 1, max_users >= start_users"
        if int(config["stage_duration_s"]) < 1:
            return "stage_duration_s must be >= 1"
        if int(config["timeout_s"]) < 1:
            return "timeout_s must be >= 1"
        if int(config["cooldown_s"]) < 0:
            return "cooldown_s must be >= 0"
    except (ValueError, TypeError):
        return "All numeric fields must be integers"

    return None


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/api/reports")
async def list_reports():
    files = sorted(glob.glob("scrubbing_report_*.json"), reverse=True)
    result = []
    for f in files:
        stat = os.stat(f)
        result.append({
            "name": os.path.basename(f),
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })
    return {"reports": result}


@app.get("/api/reports/{filename}")
async def download_report(filename: str):
    safe = Path(filename)
    if safe.parent != Path(".") or safe.suffix != ".json":
        return JSONResponse({"error": "invalid filename"}, status_code=400)
    if not safe.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(str(safe), media_type="application/json",
                        filename=filename)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global _active_task, _stop_event

    await ws.accept()
    _clients.add(ws)

    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")

            if msg_type == "start":
                if _active_task and not _active_task.done():
                    await ws.send_json({
                        "type": "error",
                        "message": "A test is already running.",
                    })
                    continue

                config = data.get("config", {})
                err = _validate_config(config)
                if err:
                    await ws.send_json({"type": "error", "message": err})
                    continue

                # Coerce numeric fields
                for key in ("start_users", "ramp_step", "max_users",
                            "stage_duration_s", "timeout_s", "cooldown_s"):
                    config[key] = int(config[key])

                _stop_event = asyncio.Event()

                async def on_update(msg):
                    await _broadcast(msg)

                _active_task = asyncio.create_task(
                    run_test(config, on_update=on_update,
                             stop_event=_stop_event)
                )

                def _on_done(task):
                    if task.cancelled():
                        return
                    exc = task.exception()
                    if exc:
                        asyncio.create_task(_broadcast({
                            "type": "error",
                            "message": str(exc),
                        }))

                _active_task.add_done_callback(_on_done)

            elif msg_type == "stop":
                if _stop_event:
                    _stop_event.set()
                if _active_task and not _active_task.done():
                    _active_task.cancel()
                await ws.send_json({
                    "type": "log",
                    "message": "Test stopped by user.",
                })

            elif msg_type == "list_reports":
                files = sorted(glob.glob("scrubbing_report_*.json"),
                               reverse=True)
                reports = []
                for f in files:
                    stat = os.stat(f)
                    reports.append({
                        "name": os.path.basename(f),
                        "size": stat.st_size,
                        "mtime": stat.st_mtime,
                    })
                await ws.send_json({"type": "reports_list", "files": reports})

    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
