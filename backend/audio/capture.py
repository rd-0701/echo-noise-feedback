"""麦克风采集：sounddevice 输入流 → 队列 → 检测引擎。"""
import queue
import threading
import logging
import numpy as np
import sounddevice as sd

from ..config import get_config
from ..core.detector import detector

logger = logging.getLogger(__name__)

_q: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=200)
_stop = threading.Event()
_worker_thread: threading.Thread | None = None
_stream = None


def _callback(indata: np.ndarray, frames: int, time_info, status) -> None:
    """音频回调：仅入队，避免阻塞。indata 为 float32 (frames, channels)。"""
    if status:
        logger.debug("音频流状态: %s", status)
    try:
        _q.put_nowait(indata.copy())
    except queue.Full:
        pass  # 处理不过来时丢弃，避免延迟累积


def _worker() -> None:
    sr = get_config()["audio"]["sample_rate"]
    while not _stop.is_set():
        try:
            block = _q.get(timeout=0.5)
        except queue.Empty:
            continue
        # 多声道取第一声道
        if block.ndim > 1:
            block = block[:, 0]
        try:
            detector.process_block(block, sr)
        except Exception as e:
            logger.exception("检测处理异常: %s", e)


def start() -> bool:
    """启动采集流与处理线程。幂等：已运行则先停止再重启。"""
    global _worker_thread, _stream
    if _stream is not None or _worker_thread is not None:
        logger.warning("音频采集已在运行，先停止再重启")
        stop()
    _stop.clear()
    cfg = get_config()["audio"]
    sr = cfg["sample_rate"]
    block = cfg["block_size"]
    device = cfg["input_device"]
    # 输出实际使用的设备信息便于诊断
    try:
        if device is None:
            dev_info = sd.query_devices(kind="input")
            dev_name = dev_info.get("name", "?") if dev_info else "默认输入"
            dev_idx = "default"
        else:
            dev_info = sd.query_devices(device)
            dev_name = dev_info.get("name", "?")
            dev_idx = device
        logger.info("使用输入设备 [index=%s]: %s", dev_idx, dev_name)
        # 同时输出到 stdout 便于用户看到
        print(f"[音频] 输入设备: {dev_name} (index={dev_idx}, sr={sr}, block={block})")
    except Exception as e:
        logger.warning("查询输入设备信息失败: %s", e)
        print(f"[音频] 警告: 无法查询输入设备信息: {e}")
    try:
        _stream = sd.InputStream(
            device=device, samplerate=sr, blocksize=block,
            channels=1, dtype="float32", callback=_callback,
        )
        _stream.start()
    except Exception as e:
        logger.exception("音频输入流启动失败: %s", e)
        emit_alert(f"麦克风启动失败: {e}")
        return False
    _worker_thread = threading.Thread(target=_worker, daemon=True, name="audio-worker")
    _worker_thread.start()
    logger.info("音频采集已启动 (sr=%d block=%d device=%s)", sr, block, device)
    return True


def stop() -> None:
    global _stream, _worker_thread
    _stop.set()
    if _stream is not None:
        try:
            _stream.stop()
            _stream.close()
        except Exception:
            pass
        _stream = None
    if _worker_thread is not None:
        _worker_thread.join(timeout=2)
        _worker_thread = None


def emit_alert(msg: str) -> None:
    from ..core.events import emit
    emit("alert", msg=msg)


def list_input_devices() -> list:
    """列出可用输入设备。"""
    try:
        devs = sd.query_devices()
    except Exception as e:
        logger.warning("查询音频设备失败: %s", e)
        return []
    result = []
    for i, d in enumerate(devs):
        if d["max_input_channels"] > 0:
            result.append({"index": i, "name": d["name"],
                           "channels": d["max_input_channels"],
                           "default_sr": d["default_samplerate"]})
    return result


def list_output_devices() -> list:
    try:
        devs = sd.query_devices()
    except Exception as e:
        logger.warning("查询音频设备失败: %s", e)
        return []
    result = []
    for i, d in enumerate(devs):
        if d["max_output_channels"] > 0:
            result.append({"index": i, "name": d["name"],
                           "channels": d["max_output_channels"],
                           "default_sr": d["default_samplerate"]})
    return result
