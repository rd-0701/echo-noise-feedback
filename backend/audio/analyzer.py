"""噪音分析：RMS / 分贝 / 频谱重心。

单位说明：
- RMS：音频信号均方根，范围 0-1（float32 PCM）
- dBFS：满量程分贝，范围 -∞ 到 0（0 = 最大振幅）
- dB SPL：声压级，范围 0-120+（环境噪音通常 30-80）
- 转换：dB_SPL ≈ dBFS + calibration_offset（默认 90，典型笔记本麦克风灵敏度）
"""
import numpy as np

# 默认校准偏移：把 dBFS 偏移到估算的 dB SPL
# 90 dB 是典型笔记本/手机麦克风的经验值，使环境噪音落在 30-80 SPL 合理区间
DEFAULT_CALIBRATION_OFFSET_DB = 90.0


def compute_rms(block: np.ndarray) -> float:
    """计算 RMS。block 为 float32 一维数组。"""
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(block))))


def rms_to_dbfs(rms: float) -> float:
    """RMS 转 dBFS（满量程分贝，范围 -∞ 到 0）。"""
    if rms <= 1e-10:
        return -100.0
    return 20.0 * np.log10(rms)


def dbfs_to_spl(dbfs: float, offset: float = DEFAULT_CALIBRATION_OFFSET_DB) -> float:
    """dBFS 转估算的 dB SPL。offset 为校准偏移。"""
    return dbfs + offset


def rms_to_db(rms: float, offset: float = DEFAULT_CALIBRATION_OFFSET_DB) -> float:
    """RMS 直接转 dB SPL（估算）。加校准偏移。

    兼容旧调用：原来 offset 默认 0，现在默认 90（SPL 校准）。
    """
    return dbfs_to_spl(rms_to_dbfs(rms), offset)


def spectral_centroid(block: np.ndarray, sample_rate: int) -> float:
    """频谱重心（Hz），用于区分稳态噪音 vs. 突发撞击。"""
    if block.size == 0:
        return 0.0
    # 加汉宁窗减少频谱泄漏
    windowed = block * np.hanning(len(block))
    mag = np.abs(np.fft.rfft(windowed))
    total = mag.sum()
    if total <= 1e-10:
        return 0.0
    freqs = np.fft.rfftfreq(len(block), 1.0 / sample_rate)
    return float((freqs * mag).sum() / total)


def analyze_block(block: np.ndarray, sample_rate: int, offset: float = DEFAULT_CALIBRATION_OFFSET_DB) -> dict:
    """一次性返回 RMS / dBFS / dB SPL / 频谱重心。

    返回字段：
    - rms: 原始 RMS 振幅
    - dbfs: 满量程分贝（-∞ 到 0）
    - db: 估算的 dB SPL（= dbfs + offset）
    - centroid_hz: 频谱重心
    """
    rms = compute_rms(block)
    dbfs = rms_to_dbfs(rms)
    db = dbfs_to_spl(dbfs, offset)
    centroid = spectral_centroid(block, sample_rate)
    return {"rms": rms, "dbfs": dbfs, "db": db, "centroid_hz": centroid}
