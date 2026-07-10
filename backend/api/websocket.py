"""WebSocket 实时推送：订阅事件总线并转发到所有连接。"""
import json
import asyncio
import threading
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..auth import authorize_ws
from ..core.events import bus

router = APIRouter()


class WSManager:
    def __init__(self):
        self.active: set[WebSocket] = set()
        self._lock = threading.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        with self._lock:
            self.active.add(ws)

    def disconnect(self, ws: WebSocket) -> None:
        with self._lock:
            self.active.discard(ws)


ws_manager = WSManager()
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


async def _broadcast(msg: dict) -> None:
    text = json.dumps(msg, ensure_ascii=False)
    with ws_manager._lock:
        conns = list(ws_manager.active)
    dead = []
    for ws in conns:
        try:
            await ws.send_text(text)
        except Exception:
            dead.append(ws)
    if dead:
        with ws_manager._lock:
            for ws in dead:
                ws_manager.active.discard(ws)


def _relay(msg: dict) -> None:
    """事件总线回调：从音频线程桥接到 asyncio 事件循环。"""
    if _loop is not None and _loop.is_running():
        _loop.call_soon_threadsafe(asyncio.ensure_future, _broadcast(msg))


bus.subscribe(_relay)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    if not authorize_ws(ws):
        await ws.close(code=4401)
        return
    await ws_manager.connect(ws)
    try:
        while True:
            # 接收客户端心跳/指令
            data = await ws.receive_text()
            # 简单协议：客户端可发 {"cmd":"ping"}
            try:
                msg = json.loads(data)
                if msg.get("cmd") == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
    except Exception:
        ws_manager.disconnect(ws)
        try:
            await ws.close()
        except Exception:
            pass
