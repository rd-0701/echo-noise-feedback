"""内置反馈音合成：L1 嗡声 / L2 脉冲 / L3 扫频。开机时自动生成。"""
import os
import numpy as np
from scipy.io import wavfile
from ..config import SOUNDS_DIR

SR = 44100

BUILTIN_SOUNDS = [
    {"id": "l1_hum", "name": "L1 低频嗡声", "type": "builtin"},
    {"id": "l2_pulse", "name": "L2 低频脉冲", "type": "builtin"},
    {"id": "l3_sweep", "name": "L3 低频扫频", "type": "builtin"},
    {"id": "alert_beep", "name": "高频蜂鸣 3kHz", "type": "builtin"},
    {"id": "alert_siren", "name": "警报扫频 0.8-2.5kHz", "type": "builtin"},
    {"id": "alert_buzzer", "name": "双音蜂鸣 2+4kHz", "type": "builtin"},
    {"id": "alert_chime", "name": "急促铃声", "type": "builtin"},
]


def _save(name: str, data: np.ndarray) -> str:
    path = os.path.join(SOUNDS_DIR, f"{name}.wav")
    # 归一化到 16-bit PCM
    peak = np.max(np.abs(data))
    if peak > 0:
        data = data / peak * 0.9
    wavfile.write(path, SR, (data * 32767).astype(np.int16))
    return path


def _gen_l1_hum(duration_s: float = 4.0) -> np.ndarray:
    """L1: 50-80Hz 正弦叠加 + 轻微 AM 调制，持续 4 秒。"""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    sig = (0.6 * np.sin(2 * np.pi * 50 * t)
           + 0.4 * np.sin(2 * np.pi * 80 * t))
    # AM 调制（2Hz，制造"嗡嗡"感）
    sig *= (0.85 + 0.15 * np.sin(2 * np.pi * 2 * t))
    # 淡入淡出避免爆音
    fade = int(SR * 0.05)
    sig[:fade] *= np.linspace(0, 1, fade)
    sig[-fade:] *= np.linspace(1, 0, fade)
    return sig


def _gen_l2_pulse(duration_s: float = 8.0) -> np.ndarray:
    """L2: 40-100Hz 短脉冲（0.3s on / 0.5s off）重复 8 秒。"""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    sig = np.zeros_like(t)
    on_s, off_s = 0.3, 0.5
    period = on_s + off_s
    pos = 0.0
    while pos < duration_s:
        start = int(pos * SR)
        end = int((pos + on_s) * SR)
        if end > len(sig):
            end = len(sig)
        seg_t = np.linspace(0, on_s, end - start, endpoint=False)
        sig[start:end] = (0.7 * np.sin(2 * np.pi * 60 * seg_t)
                          + 0.3 * np.sin(2 * np.pi * 100 * seg_t))
        pos += period
    # 每个脉冲淡入淡出
    fade = int(SR * 0.02)
    for i in range(0, len(sig), int(period * SR)):
        if i + fade < len(sig):
            sig[i:i + fade] *= np.linspace(0, 1, fade)
        if i + int(on_s * SR) - fade > 0 and i + int(on_s * SR) < len(sig):
            j = i + int(on_s * SR)
            sig[j - fade:j] *= np.linspace(1, 0, fade)
    return sig


def _gen_l3_sweep(duration_s: float = 15.0) -> np.ndarray:
    """L3: 30-150Hz 线性扫频 + 随机间隔静默，持续 15 秒。"""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    sig = np.zeros_like(t)
    # 多段扫频，随机间隔
    pos = 0.0
    rng = np.random.default_rng(42)
    while pos < duration_s:
        seg_len = rng.uniform(0.8, 1.5)
        if pos + seg_len > duration_s:
            seg_len = duration_s - pos
        seg_samples = int(seg_len * SR)
        if seg_samples <= 0:
            break
        seg_t = np.linspace(0, seg_len, seg_samples, endpoint=False)
        f0 = 30.0
        f1 = rng.uniform(120, 150)
        # 线性扫频
        phase = 2 * np.pi * (f0 * seg_t + (f1 - f0) / (2 * seg_len) * seg_t ** 2)
        start_idx = int(pos * SR)
        end_idx = start_idx + seg_samples
        if end_idx > len(sig):
            end_idx = len(sig)
            seg_t = seg_t[:end_idx - start_idx]
            phase = phase[:end_idx - start_idx]
        sig[start_idx:end_idx] = np.sin(phase)
        # 随机静默
        pos += seg_len + rng.uniform(0.2, 0.6)
    # 淡入淡出
    fade = int(SR * 0.05)
    sig[:fade] *= np.linspace(0, 1, fade)
    sig[-fade:] *= np.linspace(1, 0, fade)
    return sig


def _gen_alert_beep(duration_s: float = 3.0) -> np.ndarray:
    """高频蜂鸣：3000Hz 方波，0.2s 响 / 0.15s 停 交替，极具穿透力。"""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    sig = np.zeros_like(t)
    on_s, off_s = 0.2, 0.15
    period = on_s + off_s
    pos = 0.0
    while pos < duration_s:
        start = int(pos * SR)
        end = int((pos + on_s) * SR)
        if end > len(sig):
            end = len(sig)
        seg_t = np.linspace(0, on_s, end - start, endpoint=False)
        # 方波（含丰富奇次谐波，非常刺耳）
        sig[start:end] = np.sign(np.sin(2 * np.pi * 3000 * seg_t))
        pos += period
    # 每段淡入淡出
    fade = int(SR * 0.005)
    for i in range(0, len(sig), int(period * SR)):
        if i + fade < len(sig):
            sig[i:i + fade] *= np.linspace(0, 1, fade)
        j = i + int(on_s * SR)
        if j - fade > 0 and j < len(sig):
            sig[j - fade:j] *= np.linspace(1, 0, fade)
    return sig


def _gen_alert_siren(duration_s: float = 5.0) -> np.ndarray:
    """警报扫频：800-2500Hz 来回扫频，类似防空警报。"""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    # 1秒一个周期的线性扫频 800→2500→800（向量化实现）
    cycle = 1.0
    c = (t % cycle) / cycle
    freq = np.where(c < 0.5,
                    800 + (2500 - 800) * (c * 2),
                    2500 - (2500 - 800) * ((c - 0.5) * 2))
    # 累积相位（向量化 cumsum）
    phase = np.cumsum(2 * np.pi * freq / SR)
    sig = np.sin(phase)
    # 叠加方波分量增加刺耳感
    sig = 0.7 * sig + 0.3 * np.sign(np.sin(phase))
    fade = int(SR * 0.05)
    sig[:fade] *= np.linspace(0, 1, fade)
    sig[-fade:] *= np.linspace(1, 0, fade)
    return sig


def _gen_alert_buzzer(duration_s: float = 4.0) -> np.ndarray:
    """双音蜂鸣：2000Hz + 4000Hz 叠加，持续刺耳。"""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    sig = (0.5 * np.sign(np.sin(2 * np.pi * 2000 * t))
           + 0.5 * np.sign(np.sin(2 * np.pi * 4000 * t)))
    # 0.15s 响 / 0.1s 停（向量化包络）
    on_s, off_s = 0.15, 0.1
    period = on_s + off_s
    envelope = ((t % period) < on_s).astype(np.float64)
    # 平滑包络边缘
    fade = int(SR * 0.003)
    for i in range(0, len(t), int(period * SR)):
        if i + fade < len(t):
            envelope[i:i + fade] *= np.linspace(0, 1, fade)
    sig *= envelope
    return sig


def _gen_alert_chime(duration_s: float = 4.0) -> np.ndarray:
    """急促铃声：高频短音 3kHz→2.5kHz→2kHz 递降，每 0.3s 一个。"""
    t = np.linspace(0, duration_s, int(SR * duration_s), endpoint=False)
    sig = np.zeros_like(t)
    tones = [3000, 2500, 2000, 3000, 2500, 2000, 3000, 2500, 2000, 3000, 2500, 2000, 3000]
    tone_dur = 0.3
    for i, freq in enumerate(tones):
        start = int(i * tone_dur * SR)
        end = int((i + 1) * tone_dur * SR)
        if start >= len(sig):
            break
        if end > len(sig):
            end = len(sig)
        seg_t = np.linspace(0, tone_dur, end - start, endpoint=False)
        sig[start:end] = np.sign(np.sin(2 * np.pi * freq * seg_t))
    # 淡入淡出
    fade = int(SR * 0.008)
    for i in range(0, len(sig), int(tone_dur * SR)):
        if i + fade < len(sig):
            sig[i:i + fade] *= np.linspace(0, 1, fade)
        j = i + int(tone_dur * SR)
        if j - fade > 0 and j < len(sig):
            sig[j - fade:j] *= np.linspace(1, 0, fade)
    return sig


def ensure_builtin_sounds() -> None:
    """开机时若内置音频缺失则自动生成。"""
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    generators = {
        "l1_hum": _gen_l1_hum,
        "l2_pulse": _gen_l2_pulse,
        "l3_sweep": _gen_l3_sweep,
        "alert_beep": _gen_alert_beep,
        "alert_siren": _gen_alert_siren,
        "alert_buzzer": _gen_alert_buzzer,
        "alert_chime": _gen_alert_chime,
    }
    for sid, gen_fn in generators.items():
        path = os.path.join(SOUNDS_DIR, f"{sid}.wav")
        if not os.path.exists(path):
            _save(sid, gen_fn())


def synthesize_sound(sound_id: str, name: str, kind: str,
                     f0: float, f1: float, duration_s: float,
                     sample_rate: int = SR) -> str:
    """通用合成：扫频/低频音。kind: 'sweep' | 'tone'。返回生成文件路径。"""
    t = np.linspace(0, duration_s, int(sample_rate * duration_s), endpoint=False)
    if kind == "sweep":
        phase = 2 * np.pi * (f0 * t + (f1 - f0) / (2 * duration_s) * t ** 2)
        sig = np.sin(phase)
    else:  # tone
        sig = np.sin(2 * np.pi * f0 * t)
        if f1 != f0:
            sig = 0.5 * sig + 0.5 * np.sin(2 * np.pi * f1 * t)
    fade = int(sample_rate * 0.05)
    if fade * 2 < len(sig):
        sig[:fade] *= np.linspace(0, 1, fade)
        sig[-fade:] *= np.linspace(1, 0, fade)
    path = os.path.join(SOUNDS_DIR, f"{sound_id}.wav")
    _save(sound_id, sig)
    return path
