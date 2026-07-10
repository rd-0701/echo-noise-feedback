"""环境基线学习：开机采样底噪，动态浮动阈值。"""
import time
import threading
import numpy as np


class Baseline:
    def __init__(self):
        self._lock = threading.Lock()
        self._samples: list[float] = []
        self._baseline: float | None = None
        self._start_time = time.time()
        self._last_update = 0.0
        self._params = None

    def _refresh_params(self):
        from ..config import get_config
        d = get_config()["detection"]
        self._params = {
            "learn_seconds": d["baseline_learn_seconds"],
            "update_interval": d["baseline_update_interval_seconds"],
            "offset_db": d["threshold_offset_db"],
            "floor_db": d["absolute_threshold_db"],
        }
        return self._params

    def add_sample(self, db: float) -> None:
        with self._lock:
            p = self._refresh_params()
            self._samples.append(db)
            # 保留最近约 5 分钟（按 10Hz 估算）
            if len(self._samples) > 3000:
                self._samples = self._samples[-3000:]
            now = time.time()
            elapsed = now - self._start_time
            if (self._baseline is None
                    and elapsed >= p["learn_seconds"]
                    and len(self._samples) >= 30):
                self._baseline = float(np.median(self._samples[-300:]))
                self._last_update = now
            elif (self._baseline is not None
                  and now - self._last_update >= p["update_interval"]):
                # 缓慢适应：90% 旧 + 10% 新中位数
                new_med = float(np.median(self._samples[-300:]))
                self._baseline = 0.9 * self._baseline + 0.1 * new_med
                self._last_update = now

    @property
    def baseline(self) -> float | None:
        with self._lock:
            return self._baseline

    @property
    def threshold(self) -> float:
        with self._lock:
            p = self._refresh_params()
            if self._baseline is None:
                return p["floor_db"]
            return max(self._baseline + p["offset_db"], p["floor_db"])

    def is_learning(self) -> bool:
        with self._lock:
            return self._baseline is None

    def reset(self) -> None:
        with self._lock:
            self._samples = []
            self._baseline = None
            self._start_time = time.time()
            self._last_update = 0.0


baseline = Baseline()
