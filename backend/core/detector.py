"""噪音检测引擎：状态机 IDLE→SUSPECT→CONFIRMED→COOLDOWN，智能判定避免误触发。"""
import time
import threading
import numpy as np
from collections import deque
from datetime import datetime

from .suppression import suppression
from .baseline import baseline
from .events import emit
from ..audio.analyzer import analyze_block
from ..config import get_config
from ..db import database


class Detector:
    def __init__(self):
        self._lock = threading.Lock()
        self.state = "IDLE"          # IDLE / SUSPECT / COOLDOWN
        self._suspect_start = 0.0
        self._suspect_peak = -100.0
        self._suspect_sum = 0.0
        self._suspect_count = 0
        self._suspect_centroid_sum = 0.0
        self._current_db = -100.0
        self._current_dbfs = -100.0
        self._current_rms = 0.0
        self._current_centroid = 0.0
        self._event_count = 0
        self._last_db_emit = 0.0     # 节流时间戳
        self._last_sample_save = 0.0 # 分贝采样保存时间戳
        # 信号诊断：最近 5 秒 RMS 最大值（用于检测麦克风是否在工作）
        self._rms_max_window = deque()  # [(timestamp, rms), ...]
        self._block_count = 0        # 累计处理块数

    def process_block(self, block: np.ndarray, sample_rate: int) -> None:
        """处理一个音频块：分析 + 状态机推进 + 必要时触发反馈。"""
        cfg = get_config()
        offset = cfg["audio"]["calibration_offset"]
        info = analyze_block(block, sample_rate, offset)
        db = info["db"]
        dbfs = info["dbfs"]
        rms = info["rms"]
        centroid = info["centroid_hz"]

        self._current_db = db
        self._current_dbfs = dbfs
        self._current_rms = rms
        self._current_centroid = centroid
        self._block_count += 1

        # 维护最近 5 秒的 RMS 最大值（用于诊断麦克风信号）
        now = time.time()
        self._rms_max_window.append((now, rms))
        # 清理超过 5 秒的旧数据
        cutoff = now - 5.0
        while self._rms_max_window and self._rms_max_window[0][0] < cutoff:
            self._rms_max_window.popleft()

        # 实时推送分贝流，节流到 10Hz 防止 WS 洪泛
        if now - self._last_db_emit >= 0.1:
            self._last_db_emit = now
            emit("db", value=round(db, 1),
                 baseline=round(baseline.baseline if baseline.baseline is not None else 0, 1),
                 threshold=round(baseline.threshold, 1),
                 state=self.state)

        # 持久化分贝采样（每 5 秒存一条，用于历史趋势图）
        if now - self._last_sample_save >= 5.0:
            self._last_sample_save = now
            try:
                bl = baseline.baseline
                database.insert_db_sample(
                    datetime.now().isoformat(),
                    round(db, 1),
                    round(bl, 1) if bl is not None else None,
                    round(baseline.threshold, 1),
                )
            except Exception:
                pass

        baseline.add_sample(db)

        # 自激抑制：播放期/冷却期不检测
        if suppression.is_suppressed():
            with self._lock:
                self.state = "COOLDOWN"
            return

        # 总开关
        if not cfg["enabled"]:
            with self._lock:
                self.state = "IDLE"
            return

        threshold = baseline.threshold
        d_cfg = cfg["detection"]
        confirm_blocks = d_cfg["confirm_blocks"]
        min_duration_ms = d_cfg["min_duration_ms"]
        ignore_transient = d_cfg["ignore_transient"]
        transient_hz = d_cfg["transient_centroid_hz"]

        with self._lock:
            if db > threshold:
                if self.state == "IDLE":
                    self.state = "SUSPECT"
                    self._suspect_start = time.time()
                    self._suspect_peak = db
                    self._suspect_sum = db
                    self._suspect_count = 1
                    self._suspect_centroid_sum = centroid
                elif self.state == "SUSPECT":
                    self._suspect_peak = max(self._suspect_peak, db)
                    self._suspect_sum += db
                    self._suspect_count += 1
                    self._suspect_centroid_sum += centroid
                    duration_ms = int((time.time() - self._suspect_start) * 1000)
                    if self._suspect_count >= confirm_blocks:
                        avg_centroid = (self._suspect_centroid_sum
                                        / self._suspect_count)
                        # 智能过滤：高频瞬态撞击（如敲门）
                        if (ignore_transient
                                and avg_centroid > transient_hz
                                and duration_ms < min_duration_ms * 2):
                            self._reset_to_idle()
                            return
                        if duration_ms < min_duration_ms:
                            # 持续时长不足，继续累积
                            return
                        # 确认噪音事件
                        self._confirm_event(
                            self._suspect_peak,
                            self._suspect_sum / self._suspect_count,
                            duration_ms, avg_centroid)
                        self.state = "COOLDOWN"
                # COOLDOWN 状态下忽略
            else:
                # 低于阈值
                if self.state == "SUSPECT":
                    duration_ms = int((time.time() - self._suspect_start) * 1000)
                    # 未达确认但持续够久，记录为未触发事件
                    if (self._suspect_count >= 3
                            and duration_ms >= min_duration_ms):
                        avg_centroid = (self._suspect_centroid_sum
                                        / self._suspect_count)
                        self._record_event(
                            self._suspect_peak,
                            self._suspect_sum / self._suspect_count,
                            duration_ms, avg_centroid, level=None)
                    self._reset_to_idle()
                elif self.state == "COOLDOWN":
                    self._reset_to_idle()

    def _reset_to_idle(self):
        self.state = "IDLE"
        self._suspect_count = 0
        self._suspect_peak = -100.0
        self._suspect_sum = 0.0
        self._suspect_centroid_sum = 0.0

    def _confirm_event(self, peak_db: float, avg_db: float,
                       duration_ms: int, centroid: float) -> None:
        ts = datetime.now().isoformat()
        from .strategy import decide_level, trigger_feedback
        level = decide_level(peak_db)
        database.insert_noise_event(ts, round(peak_db, 1), round(avg_db, 1),
                                    duration_ms, level, round(centroid, 1))
        self._event_count += 1
        # auto_feedback 控制是否自动播放反馈
        cfg = get_config()
        auto_fb = cfg.get("auto_feedback", True)
        emit("event", ts=ts, peak_db=round(peak_db, 1), avg_db=round(avg_db, 1),
             duration_ms=duration_ms, level=level,
             centroid_hz=round(centroid, 1), triggered=auto_fb)
        if auto_fb:
            trigger_feedback(level, peak_db, source="noise")

    def _record_event(self, peak_db: float, avg_db: float,
                      duration_ms: int, centroid: float,
                      level: int | None) -> None:
        ts = datetime.now().isoformat()
        database.insert_noise_event(ts, round(peak_db, 1), round(avg_db, 1),
                                    duration_ms, level, round(centroid, 1))
        emit("event", ts=ts, peak_db=round(peak_db, 1), avg_db=round(avg_db, 1),
             duration_ms=duration_ms, level=level,
             centroid_hz=round(centroid, 1), triggered=False)

    @property
    def current_db(self) -> float:
        return self._current_db

    @property
    def current_dbfs(self) -> float:
        return self._current_dbfs

    @property
    def current_rms(self) -> float:
        return self._current_rms

    @property
    def current_centroid(self) -> float:
        return self._current_centroid

    @property
    def event_count(self) -> int:
        return self._event_count

    @property
    def recent_rms_max(self) -> float:
        """最近 5 秒 RMS 最大值（用于诊断麦克风信号是否正常）。"""
        if not self._rms_max_window:
            return 0.0
        return max(r for _, r in self._rms_max_window)

    @property
    def block_count(self) -> int:
        return self._block_count


detector = Detector()
