"""WebSocket handler for real-time progress and log streaming."""
import json, logging, asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_clients: set[WebSocket] = set()
_message_queue: asyncio.Queue | None = None


class WebSocketLogHandler(logging.Handler):
    """Intercepts log messages and forwards to all WebSocket clients."""

    def emit(self, record):
        if _message_queue is None:
            return
        msg = {
            "type": "log",
            "level": record.levelname.lower(),
            "message": self.format(record),
        }
        try:
            _message_queue.put_nowait(msg)
        except asyncio.QueueFull:
            pass


def install_log_handler():
    """Attach WebSocket log handler to the wabbajack logger."""
    handler = WebSocketLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("wabbajack").addHandler(handler)
    return handler


async def broadcast(msg: dict):
    """Send a message to all connected WebSocket clients."""
    data = json.dumps(msg)
    dead = set()
    for ws in _clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    _clients -= dead


def push_progress(phase, current, total, speed="", eta=""):
    """Push progress update from sync code (installer threads)."""
    if _message_queue is None:
        return
    try:
        _message_queue.put_nowait({
            "type": "progress",
            "phase": phase,
            "current": current,
            "total": total,
            "speed": speed,
            "eta": eta,
        })
    except asyncio.QueueFull:
        pass


def push_event(event_type, **kwargs):
    """Push arbitrary event from sync code."""
    if _message_queue is None:
        return
    try:
        _message_queue.put_nowait({"type": event_type, **kwargs})
    except asyncio.QueueFull:
        pass


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global _message_queue
    await ws.accept()
    _clients.add(ws)

    if _message_queue is None:
        _message_queue = asyncio.Queue(maxsize=10000)

    async def drain():
        while True:
            try:
                msg = await asyncio.wait_for(_message_queue.get(), timeout=0.1)
                await broadcast(msg)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    drain_task = asyncio.create_task(drain())

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "cancel":
                push_event("cancel_requested")
            elif msg.get("type") == "skip_file":
                push_event("skip_file", name=msg.get("name", ""))
            elif msg.get("type") == "manual_complete":
                push_event("manual_complete", name=msg.get("name", ""))
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(ws)
        if not _clients:
            drain_task.cancel()
