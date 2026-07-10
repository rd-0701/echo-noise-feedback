"""FastAPI 入口：挂载路由、静态文件、启动后台音频/调度/蓝牙线程。"""
import os
import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from .config import (load_config, ensure_dirs, SOUNDS_DIR, BASE_DIR)
from .auth import auth_middleware, get_token
from .db import database
from .audio import sounds as sounds_mod
from .audio import capture, bluetooth
from .core import scheduler as sched_mod
from .core.events import emit
from .api.routes import router as routes_router
from .api.websocket import router as ws_router, set_loop
from .api.workshop import router as workshop_router
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("echo")


def _register_builtin_sounds() -> None:
    """将内置声音注册到数据库（若未注册）。"""
    for s in sounds_mod.BUILTIN_SOUNDS:
        path = os.path.join(SOUNDS_DIR, f"{s['id']}.wav")
        if not os.path.exists(path):
            continue
        if database.get_sound(s["id"]) is None:
            try:
                sr, data = sounds_mod.wavfile.read(path)
                dur = int(len(data) / sr * 1000)
            except Exception:
                dur = None
            database.upsert_sound(s["id"], s["name"], s["type"], path, dur,
                                  datetime.now().isoformat())


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ===== 启动 =====
    ensure_dirs()
    load_config()
    database.init_db()
    # 清理过期数据，防止数据库无限增长
    try:
        database.cleanup_old_samples(30)
        database.cleanup_old_events(90)
    except Exception:
        pass
    sounds_mod.ensure_builtin_sounds()
    _register_builtin_sounds()
    # 捕获事件循环供 WebSocket 桥接
    set_loop(asyncio.get_running_loop())
    # 启动音频采集
    ok = capture.start()
    if not ok:
        logger.warning("音频采集启动失败，检测功能不可用（Web 服务仍可用）")
    # 启动蓝牙监控
    bluetooth.start()
    # 启动定时调度
    sched_mod.start()
    emit("info", msg="系统已启动")
    logger.info("Echo 系统已启动。Token: %s", get_token())
    yield
    # ===== 关闭 =====
    emit("info", msg="系统已停止")  # 先发再停，避免向已关闭的 loop 投递
    sched_mod.stop()
    bluetooth.stop()
    capture.stop()
    database.close()
    logger.info("Echo 系统已停止")


app = FastAPI(title="Echo 噪音反馈系统", lifespan=lifespan)

# CORS（便于本地调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        return await auth_middleware(request, call_next)


app.add_middleware(AuthMiddleware)

# 路由
app.include_router(routes_router)
app.include_router(ws_router)
app.include_router(workshop_router)


@app.get("/health")
def health():
    return {"ok": True}


# 静态前端（frontend 目录）
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


def run() -> None:
    """命令行启动入口。"""
    import uvicorn
    cfg = load_config()
    uvicorn.run(
        "backend.main:app",
        host=cfg["server"]["host"],
        port=cfg["server"]["port"],
        reload=False,
        log_level="info",
    )


def run_in_thread() -> threading.Thread:
    """托盘模式：在后台线程启动 uvicorn，返回该线程。"""
    import uvicorn
    cfg = load_config()
    config = uvicorn.Config(
        "backend.main:app",
        host=cfg["server"]["host"],
        port=cfg["server"]["port"],
        log_level="info",
    )
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True, name="uvicorn")
    t.start()
    return t


if __name__ == "__main__":
    run()
