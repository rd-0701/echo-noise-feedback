"""SQLite 建表语句。"""
SCHEMA = """
CREATE TABLE IF NOT EXISTS noise_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    peak_db REAL NOT NULL,
    avg_db REAL NOT NULL,
    duration_ms INTEGER NOT NULL,
    level_triggered INTEGER,
    centroid_hz REAL
);

CREATE TABLE IF NOT EXISTS playbacks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    sound_id TEXT NOT NULL,
    level INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    source TEXT NOT NULL,
    volume REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sounds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    path TEXT NOT NULL,
    duration_ms INTEGER,
    created_ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS db_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    db REAL NOT NULL,
    baseline REAL,
    threshold REAL
);

CREATE INDEX IF NOT EXISTS idx_noise_ts ON noise_events(ts);
CREATE INDEX IF NOT EXISTS idx_playback_ts ON playbacks(ts);
CREATE INDEX IF NOT EXISTS idx_db_samples_ts ON db_samples(ts);
"""
