"""反馈音播放：输出到系统默认音频设备（蓝牙音响）。"""
import os
import threading
import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from ..core.suppression import suppression
from ..config import get_config, SOUNDS_DIR
from ..db import database
from ..core.events import emit
from datetime import datetime

_play_lock = threading.Lock()


def _resolve_path(sound_id: str) -> str | None:
    """查找声音文件路径：先查库，再查内置目录。"""
    row = database.get_sound(sound_id)
    if row is not None:
        path = row["path"]
        if os.path.exists(path):
            return path
    # 内置声音
    path = os.path.join(SOUNDS_DIR, f"{sound_id}.wav")
    if os.path.exists(path):
        return path
    return None


def play_sound(sound_id: str, level: int, source: str,
               volume: float = 0.8, blocking: bool = False) -> bool:
    """播放指定声音。source: 'noise'/'scheduled'/'manual'。返回是否成功。"""
    path = _resolve_path(sound_id)
    if path is None:
        emit("alert", msg=f"音频不存在: {sound_id}")
        return False

    try:
        sr, data = wavfile.read(path)
    except Exception as e:
        emit("alert", msg=f"音频读取失败: {e}")
        return False
    if data.ndim > 1:
        data = data[:, 0]
    data = data.astype(np.float32) / 32767.0
    data = data * float(np.clip(volume, 0.0, 1.0))

    def _run():
        suppression.start_playback()
        try:
            cfg = get_config()["audio"]
            out_device = cfg.get("output_device")
            sd.play(data, sr, device=out_device)
            duration_ms = int(len(data) / sr * 1000)
            ts = datetime.now().isoformat()
            try:
                database.insert_playback(ts, sound_id, level, duration_ms, source, volume)
            except Exception:
                pass
            emit("playback", ts=ts, sound_id=sound_id, level=level,
                 duration_ms=duration_ms, source=source, volume=round(volume, 2))
            sd.wait()
        except Exception as e:
            emit("alert", msg=f"播放失败: {e}")
        finally:
            cooldown = get_config()["suppression"]["cooldown_s"]
            suppression.end_playback(cooldown)

    if blocking:
        with _play_lock:
            _run()
    else:
        threading.Thread(target=_run, daemon=True).start()
    return True
