"""定时调度：在设定时间窗内按间隔自动播放反馈。"""
import threading
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import get_config, update_config
from .strategy import trigger_feedback
from .events import emit

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_lock = threading.Lock()


def _scheduled_fire():
    """定时触发回调：按配置的固定等级播放。"""
    try:
        cfg = get_config()
        if not cfg["enabled"]:
            return
        level = cfg["scheduler"].get("level", 1)
        emit("info", msg=f"定时触发 L{level}")
        trigger_feedback(level, current_db=0.0, source="scheduled")
    except Exception as e:
        logger.exception("定时触发异常: %s", e)


def _rebuild():
    """根据当前配置重建调度任务。"""
    global _scheduler
    with _lock:
        if _scheduler is not None:
            try:
                _scheduler.shutdown(wait=False)
            except Exception:
                pass
            _scheduler = None
        cfg = get_config()
        sc = cfg["scheduler"]
        if not sc.get("enabled"):
            return
        _scheduler = BackgroundScheduler(daemon=True)
        try:
            start_t = sc["start_time"]   # "HH:MM"
            end_t = sc["end_time"]
            sh, sm = map(int, start_t.split(":"))
            eh, em = map(int, end_t.split(":"))
            interval = int(sc["interval_minutes"])
            # 在每日 [start, end] 区间内每 interval 分钟触发
            # 跨日时拆成 [sh, 24) + [0, eh) 两个区间
            hours = list(range(sh, eh)) if sh < eh else list(range(sh, 24)) + list(range(0, eh))
            if not hours:
                return
            hour_str = ",".join(str(h) for h in hours)
            trigger = CronTrigger(hour=hour_str, minute=f"*/{interval}")
            _scheduler.add_job(_scheduled_fire, trigger, id="scheduled_fire",
                               max_instances=1, coalesce=True)
            _scheduler.start()
            logger.info("定时调度已启动: %s-%s 每 %d 分钟",
                        start_t, end_t, interval)
        except Exception as e:
            logger.exception("调度构建失败: %s", e)


def reload() -> None:
    """配置变更后重建调度。"""
    _rebuild()


def start() -> None:
    _rebuild()


def stop() -> None:
    global _scheduler
    with _lock:
        if _scheduler is not None:
            try:
                _scheduler.shutdown(wait=False)
            except Exception:
                pass
            _scheduler = None
