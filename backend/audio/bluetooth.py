"""蓝牙音响连接状态监控：定时轮询默认渲染设备状态。"""
import threading
import time
import logging

from ..config import get_config
from ..core.events import emit

logger = logging.getLogger(__name__)

_bt_state = {"connected": True, "device": None}
_lock = threading.Lock()
_stop_flag = threading.Event()
_thread: threading.Thread | None = None


def _check_default_render() -> bool:
    """通过 pycaw 查询当前默认渲染设备是否可用。"""
    try:
        from pycaw.pycaw import AudioUtilities
        # GetSpeakers 返回默认渲染设备（即用户设为默认的蓝牙音响）
        speakers = AudioUtilities.GetSpeakers()
        if speakers is None:
            return False
        return True
    except Exception:
        return _check_via_powershell()


def _check_via_powershell() -> bool:
    """PowerShell 兜底：检查是否有处于 OK 状态的音频渲染端点。"""
    try:
        import subprocess
        ps = (
            "Get-PnpDevice -Class AudioEndpoint -Status OK "
            "| Where-Object { $_.FriendlyName -notlike '*Microphone*' } "
            "| Select-Object -First 1 -ExpandProperty Status"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True, timeout=8)
        return result.stdout.strip().lower() == "ok"
    except Exception as e:
        logger.warning("PowerShell 蓝牙检测失败: %s", e)
        # 检测失败时假定连接，避免误报断开
        return True


def _check_bluetooth_connected() -> bool:
    """检查蓝牙音响连接状态。优先 pycaw，失败回退 PowerShell。"""
    return _check_default_render()


def get_status() -> dict:
    with _lock:
        return dict(_bt_state)


def is_connected() -> bool:
    with _lock:
        return _bt_state["connected"]


def _loop():
    cfg_interval = 5
    while not _stop_flag.is_set():
        try:
            interval = get_config()["bluetooth"]["poll_interval_s"]
        except Exception:
            interval = cfg_interval
        connected = _check_bluetooth_connected()
        with _lock:
            prev = _bt_state["connected"]
            _bt_state["connected"] = connected
        if connected != prev:
            emit("bt_status", connected=connected)
            if not connected:
                emit("alert", msg="蓝牙已断开")
            else:
                emit("alert", msg="蓝牙已连接")
        _stop_flag.wait(interval)


def start() -> None:
    global _thread
    _stop_flag.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="bt-monitor")
    _thread.start()


def stop() -> None:
    global _thread
    _stop_flag.set()
    if _thread is not None:
        _thread.join(timeout=10)
        _thread = None
