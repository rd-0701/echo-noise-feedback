"""配置管理：加载/持久化 JSON 配置，提供全局访问。"""
import json
import os
import threading
import copy

# 项目根目录（backend 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SOUNDS_DIR = os.path.join(BASE_DIR, "backend", "sounds")
UPLOADS_DIR = os.path.join(BASE_DIR, "backend", "uploads")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "enabled": True,
    "auto_feedback": True,       # 噪音超阈值后自动播放反馈
    "audio": {
        "sample_rate": 44100,
        "block_size": 1024,
        "input_device": None,        # None = 系统默认输入
        "output_device": None,       # None = 系统默认输出（蓝牙音响需设为默认）
        "calibration_offset": 90.0,  # dBFS→dB SPL 校准偏移（典型笔记本麦克风 90）
    },
    "detection": {
        "baseline_learn_seconds": 60,
        "baseline_update_interval_seconds": 600,
        "threshold_offset_db": 15.0,
        "absolute_threshold_db": 40.0,
        "confirm_blocks": 5,         # 连续超阈值块数确认
        "min_duration_ms": 300,      # 忽略更短事件（撞击声）
        "ignore_transient": True,
        "transient_centroid_hz": 4000,
    },
    "strategy": {
        "l1_delta_db": 8.0,          # 超阈值 0-8dB → L1
        "l2_delta_db": 18.0,         # 超阈值 8-18dB → L2，>18dB → L3
        "l1_duration_s": 4,
        "l2_duration_s": 8,
        "l3_duration_s": 15,
        "l1_sound": "alert_beep",
        "l2_sound": "alert_siren",
        "l3_sound": "alert_buzzer",
        "min_volume": 0.5,
        "max_volume": 1.0,
    },
    "scheduler": {
        "enabled": False,
        "start_time": "06:00",
        "end_time": "18:00",
        "interval_minutes": 3,
        "level": 1,
    },
    "suppression": {
        "cooldown_s": 3.0,
    },
    "bluetooth": {
        "poll_interval_s": 5,
        "device_name": None,         # None = 监控默认渲染设备
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
    },
}

_lock = threading.RLock()
_config = None


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并 override 到 base，返回新 dict。"""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def load_config() -> dict:
    global _config
    with _lock:
        if _config is not None:
            return _config
        os.makedirs(DATA_DIR, exist_ok=True)
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    stored = json.load(f)
                _config = _deep_merge(DEFAULT_CONFIG, stored)
            except (json.JSONDecodeError, OSError):
                _config = copy.deepcopy(DEFAULT_CONFIG)
        else:
            _config = copy.deepcopy(DEFAULT_CONFIG)
            save_config(_config)
        return _config


def save_config(cfg: dict = None) -> None:
    global _config
    with _lock:
        if cfg is not None:
            _config = _deep_merge(DEFAULT_CONFIG, cfg)
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_config, f, ensure_ascii=False, indent=2)


def get_config() -> dict:
    """获取当前配置（运行时单例）。"""
    if _config is None:
        return load_config()
    return _config


def update_config(partial: dict) -> dict:
    """部分更新配置（深合并）并持久化。"""
    with _lock:
        current = get_config()
        merged = _deep_merge(current, partial)
        save_config(merged)
        return merged


def ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
