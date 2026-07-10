"""三级分级播放策略：根据噪音程度选择等级与动态音量。"""
from ..audio.player import play_sound
from ..config import get_config
from ..core.baseline import baseline
from ..core.events import emit


def decide_level(peak_db: float) -> int:
    """根据 (峰值分贝 - 阈值) 决定反馈等级。"""
    cfg = get_config()["strategy"]
    threshold = baseline.threshold
    delta = peak_db - threshold
    if delta >= cfg["l2_delta_db"]:
        return 3
    if delta >= cfg["l1_delta_db"]:
        return 2
    return 1


def compute_volume(level: int, current_db: float = 0.0) -> float:
    """动态音量：噪音越大反馈越响，上限 max_volume。"""
    cfg = get_config()["strategy"]
    min_v, max_v = cfg["min_volume"], cfg["max_volume"]
    if current_db > 0:
        threshold = baseline.threshold
        delta = max(0.0, current_db - threshold)
        # delta 0-20dB 线性映射到 min_v-max_v
        ratio = min(delta / 20.0, 1.0)
        return min_v + (max_v - min_v) * ratio
    # 无分贝参考时按等级
    if level == 1:
        return min_v + (max_v - min_v) * 0.2
    if level == 2:
        return min_v + (max_v - min_v) * 0.6
    return max_v


def trigger_feedback(level: int, current_db: float = 0.0,
                     source: str = "noise") -> bool:
    """触发分级反馈播放。"""
    cfg = get_config()["strategy"]
    if level == 1:
        sound_id = cfg["l1_sound"]
    elif level == 2:
        sound_id = cfg["l2_sound"]
    else:
        sound_id = cfg["l3_sound"]
    volume = compute_volume(level, current_db)
    emit("trigger", level=level, sound_id=sound_id, volume=round(volume, 2),
         source=source)
    return play_sound(sound_id, level, source, volume=volume)
