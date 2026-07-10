"""自激循环抑制：播放期 + 冷却期屏蔽检测。

使用引用计数支持并发播放：每次 start_playback +1，每次 end_playback -1，
归零时进入冷却期。避免多个非阻塞播放互相干扰 _is_playing 状态。
"""
import time
import threading


class Suppression:
    def __init__(self):
        self._lock = threading.Lock()
        self._play_count = 0          # 引用计数，替代布尔标志
        self._cooldown_until = 0.0

    def is_suppressed(self) -> bool:
        """当前是否处于抑制状态（正在播放或冷却期内）。"""
        with self._lock:
            return self._play_count > 0 or time.time() < self._cooldown_until

    @property
    def is_playing(self) -> bool:
        with self._lock:
            return self._play_count > 0

    def start_playback(self) -> None:
        with self._lock:
            self._play_count += 1

    def end_playback(self, cooldown_s: float = 3.0) -> None:
        with self._lock:
            self._play_count = max(0, self._play_count - 1)
            if self._play_count == 0:
                self._cooldown_until = time.time() + cooldown_s

    def reset(self) -> None:
        with self._lock:
            self._play_count = 0
            self._cooldown_until = 0.0


suppression = Suppression()
