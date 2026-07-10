"""SQLite 数据库连接（线程安全）。"""
import sqlite3
import threading
import os
from .models import SCHEMA
from ..config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "echo.db")
_lock = threading.Lock()
_conn = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(DATA_DIR, exist_ok=True)
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
        _conn.commit()
    return _conn


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    with _lock:
        conn = get_conn()
        cur = conn.execute(sql, params)
        conn.commit()
        return cur


def query(sql: str, params: tuple = ()) -> list:
    with _lock:
        cur = get_conn().execute(sql, params)
        return cur.fetchall()


def query_one(sql: str, params: tuple = ()) -> sqlite3.Row | None:
    with _lock:
        cur = get_conn().execute(sql, params)
        return cur.fetchone()


def init_db() -> None:
    get_conn()


def close() -> None:
    """关闭数据库连接（应用退出时调用）。"""
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.commit()
                _conn.close()
            except Exception:
                pass
            _conn = None


# ===== 噪音事件 =====
def insert_noise_event(ts: str, peak_db: float, avg_db: float,
                       duration_ms: int, level_triggered: int | None,
                       centroid_hz: float | None) -> int:
    cur = execute(
        "INSERT INTO noise_events(ts, peak_db, avg_db, duration_ms, level_triggered, centroid_hz) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ts, peak_db, avg_db, duration_ms, level_triggered, centroid_hz),
    )
    return cur.lastrowid


def get_noise_events(start_ts: str, end_ts: str) -> list:
    return query(
        "SELECT * FROM noise_events WHERE ts >= ? AND ts <= ? ORDER BY ts ASC",
        (start_ts, end_ts),
    )


# ===== 播放记录 =====
def insert_playback(ts: str, sound_id: str, level: int, duration_ms: int,
                    source: str, volume: float) -> int:
    cur = execute(
        "INSERT INTO playbacks(ts, sound_id, level, duration_ms, source, volume) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (ts, sound_id, level, duration_ms, source, volume),
    )
    return cur.lastrowid


def get_playbacks(start_ts: str, end_ts: str) -> list:
    return query(
        "SELECT * FROM playbacks WHERE ts >= ? AND ts <= ? ORDER BY ts ASC",
        (start_ts, end_ts),
    )


# ===== 音频库 =====
def upsert_sound(sid: str, name: str, stype: str, path: str,
                 duration_ms: int | None, created_ts: str) -> None:
    execute(
        "INSERT INTO sounds(id, name, type, path, duration_ms, created_ts) "
        "VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET name=excluded.name, type=excluded.type, "
        "path=excluded.path, duration_ms=excluded.duration_ms",
        (sid, name, stype, path, duration_ms, created_ts),
    )


def get_sound(sid: str) -> sqlite3.Row | None:
    return query_one("SELECT * FROM sounds WHERE id = ?", (sid,))


def list_sounds() -> list:
    return query("SELECT * FROM sounds ORDER BY created_ts ASC")


def delete_sound(sid: str) -> None:
    execute("DELETE FROM sounds WHERE id = ?", (sid,))


# ===== 分贝采样（连续趋势） =====
def insert_db_sample(ts: str, db: float, baseline: float | None,
                     threshold: float) -> int:
    cur = execute(
        "INSERT INTO db_samples(ts, db, baseline, threshold) VALUES (?, ?, ?, ?)",
        (ts, db, baseline, threshold),
    )
    return cur.lastrowid


def get_db_samples(start_ts: str, end_ts: str, limit: int = 2000) -> list:
    """获取分贝采样，按时间升序，限制条数避免过大。"""
    return query(
        "SELECT * FROM db_samples WHERE ts >= ? AND ts <= ? "
        "ORDER BY ts ASC LIMIT ?",
        (start_ts, end_ts, limit),
    )


def cleanup_old_samples(days: int = 30) -> int:
    """删除超过指定天数的旧采样数据，防止数据库无限增长。"""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cur = execute("DELETE FROM db_samples WHERE ts < ?", (cutoff,))
    return cur.rowcount


def cleanup_old_events(days: int = 90) -> int:
    """删除超过指定天数的事件和播放记录。"""
    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    e = execute("DELETE FROM noise_events WHERE ts < ?", (cutoff,))
    p = execute("DELETE FROM playbacks WHERE ts < ?", (cutoff,))
    return e.rowcount + p.rowcount
