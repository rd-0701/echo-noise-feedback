"""事件总线：解耦音频核心与 WebSocket 推送层。"""
import threading
import logging

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self):
        self._subs = []
        self._lock = threading.Lock()

    def subscribe(self, cb) -> None:
        with self._lock:
            self._subs.append(cb)

    def unsubscribe(self, cb) -> None:
        with self._lock:
            if cb in self._subs:
                self._subs.remove(cb)

    def publish(self, msg: dict) -> None:
        with self._lock:
            subs = list(self._subs)
        for cb in subs:
            try:
                cb(msg)
            except Exception as e:
                logger.warning("事件订阅者异常: %s", e)


bus = EventBus()


def emit(msg_type: str, **payload) -> None:
    """便捷发布：emit('db', value=42.3)。"""
    bus.publish({"type": msg_type, **payload})
