"""Token 认证：首运行生成，FastAPI 中间件 + WebSocket 校验。"""
import os
import secrets
import threading
from fastapi import Request, WebSocket
from fastapi.responses import JSONResponse
from .config import DATA_DIR

TOKEN_PATH = os.path.join(DATA_DIR, "auth_token.txt")
_token: str | None = None
_token_lock = threading.Lock()


def get_token() -> str:
    """线程安全地获取/生成 Token。并发首调只生成一个。"""
    global _token
    with _token_lock:
        if _token is not None:
            return _token
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(TOKEN_PATH):
            with open(TOKEN_PATH, "r", encoding="utf-8") as f:
                _token = f.read().strip()
        else:
            _token = secrets.token_urlsafe(24)
            with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                f.write(_token)
        return _token


def is_authorized(request: Request) -> bool:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip() == get_token()
    # 也支持查询参数（方便调试/前端首次加载）
    return request.query_params.get("token") == get_token()


async def auth_middleware(request: Request, call_next):
    """中间件：保护 /api 路径，放行静态与健康检查。
    注意：BaseHTTPMiddleware 不拦截 WebSocket，WS 鉴权在 endpoint 内通过 authorize_ws 完成。
    """
    path = request.url.path
    # 放行：根页面、静态资源、健康检查
    if path in ("/", "/health") or path.startswith("/css") or path.startswith("/js") \
            or path.startswith("/assets") or path.endswith((".js", ".css", ".png", ".ico",
                                                              ".json", ".woff2", ".webmanifest")):
        return await call_next(request)
    if path.startswith("/api"):
        if not is_authorized(request):
            return JSONResponse(status_code=401, content={"detail": "未授权"})
    return await call_next(request)


def authorize_ws(ws: WebSocket) -> bool:
    token = ws.query_params.get("token", "")
    return token == get_token()
