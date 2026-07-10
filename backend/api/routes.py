"""REST 路由：状态 / 配置 / 触发 / 预览 / 历史 / 音频库 / 设备。"""
import os
import uuid
from datetime import datetime, timedelta
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import get_config, update_config
from ..db import database
from ..core.detector import detector
from ..core.baseline import baseline
from ..core.strategy import trigger_feedback, compute_volume, decide_level
from ..core.suppression import suppression
from ..core import scheduler as sched_mod
from ..audio import capture
from ..audio.player import play_sound

router = APIRouter(prefix="/api")


# ===== 状态 =====
@router.get("/status")
def status():
    cfg = get_config()
    from ..audio import bluetooth
    return {
        "enabled": cfg["enabled"],
        "auto_feedback": cfg.get("auto_feedback", True),
        "current_db": round(detector.current_db, 1),
        "current_dbfs": round(detector.current_dbfs, 1),
        "current_rms": detector.current_rms,
        "current_centroid": round(detector.current_centroid, 1),
        "baseline": round(baseline.baseline, 1) if baseline.baseline is not None else None,
        "threshold": round(baseline.threshold, 1),
        "is_learning": baseline.is_learning(),
        "detector_state": detector.state,
        "suppressed": suppression.is_suppressed(),
        "bt_connected": bluetooth.is_connected(),
        "event_count": detector.event_count,
    }


# ===== 诊断 =====
@router.get("/diagnostics")
def diagnostics():
    """诊断信息：用于排查麦克风/分贝/触发问题。"""
    cfg = get_config()
    from ..audio import bluetooth
    # 麦克风信号诊断
    recent_rms_max = detector.recent_rms_max
    recent_rms_max_dbfs = 20 * np.log10(recent_rms_max) if recent_rms_max > 1e-10 else -100.0
    # 判断麦克风状态
    if detector.block_count == 0:
        mic_status = "未启动"
    elif recent_rms_max < 1e-6:
        mic_status = "无信号（可能麦克风未连接或音量为0）"
    elif recent_rms_max < 1e-4:
        mic_status = "信号极弱"
    elif recent_rms_max < 1e-2:
        mic_status = "信号正常"
    else:
        mic_status = "信号良好"
    return {
        "mic_status": mic_status,
        "mic_signal_strength": (
            "无" if recent_rms_max < 1e-6 else
            "极弱" if recent_rms_max < 1e-4 else
            "正常" if recent_rms_max < 1e-2 else "良好"
        ),
        "current_rms": detector.current_rms,
        "current_dbfs": round(detector.current_dbfs, 2),
        "current_db_spl": round(detector.current_db, 2),
        "recent_5s_rms_max": recent_rms_max,
        "recent_5s_dbfs_max": round(recent_rms_max_dbfs, 2),
        "recent_5s_db_spl_max": round(recent_rms_max_dbfs + cfg["audio"]["calibration_offset"], 2),
        "calibration_offset": cfg["audio"]["calibration_offset"],
        "baseline": round(baseline.baseline, 2) if baseline.baseline is not None else None,
        "threshold": round(baseline.threshold, 2),
        "absolute_threshold_db": cfg["detection"]["absolute_threshold_db"],
        "threshold_offset_db": cfg["detection"]["threshold_offset_db"],
        "block_count": detector.block_count,
        "detector_state": detector.state,
        "auto_feedback": cfg.get("auto_feedback", True),
        "enabled": cfg["enabled"],
        "suppressed": suppression.is_suppressed(),
        "bt_connected": bluetooth.is_connected(),
        "input_device": cfg["audio"]["input_device"],
        "sample_rate": cfg["audio"]["sample_rate"],
        "block_size": cfg["audio"]["block_size"],
        "event_count": detector.event_count,
        "explanation": (
            f"当前分贝 {round(detector.current_db, 1)} dB SPL（估算），"
            f"阈值 {round(baseline.threshold, 1)} dB。"
            + ("自动反馈已开启，噪音超阈值将自动播放。" if cfg.get("auto_feedback", True)
               else "自动反馈已关闭。")
            + (f"最近5秒最大RMS={recent_rms_max:.6f}（{mic_status}）。"
               if detector.block_count > 0 else "采集未启动。")
        ),
    }


# ===== 配置 =====
@router.get("/config")
def get_cfg():
    return get_config()


class ConfigUpdate(BaseModel):
    config: dict


@router.put("/config")
def put_cfg(payload: ConfigUpdate):
    new_cfg = update_config(payload.config)
    # 配置变更后重建调度
    sched_mod.reload()
    return new_cfg


# ===== 主开关 =====
class TogglePayload(BaseModel):
    enabled: bool


@router.post("/toggle")
def toggle(payload: TogglePayload):
    update_config({"enabled": payload.enabled})
    return {"enabled": payload.enabled}


class AutoFeedbackPayload(BaseModel):
    auto_feedback: bool


@router.post("/auto-feedback")
def set_auto_feedback(payload: AutoFeedbackPayload):
    """开关自动反馈：噪音超阈值后是否自动播放。"""
    update_config({"auto_feedback": payload.auto_feedback})
    return {"auto_feedback": payload.auto_feedback}


# ===== 手动触发 =====
class TriggerPayload(BaseModel):
    level: int | None = None      # 1/2/3，None=按当前分贝判定
    volume: float | None = None
    sound_id: str | None = None   # 指定音频，None=按等级默认


@router.post("/trigger")
def trigger(payload: TriggerPayload):
    from ..audio import bluetooth
    if not bluetooth.is_connected():
        raise HTTPException(409, "蓝牙已断开，无法播放")
    # level=None 表示按当前分贝自动判定等级
    if payload.level is None:
        level = decide_level(detector.current_db)
    else:
        level = payload.level
    if payload.sound_id:
        vol = payload.volume if payload.volume is not None else compute_volume(level, detector.current_db)
        ok = play_sound(payload.sound_id, level, "manual", volume=vol)
    else:
        ok = trigger_feedback(level, detector.current_db, source="manual")
    return {"ok": ok, "level": level}


# ===== 预览播放 =====
class PreviewPayload(BaseModel):
    sound_id: str
    volume: float = 0.8


@router.post("/preview")
def preview(payload: PreviewPayload):
    from ..audio import bluetooth
    if not bluetooth.is_connected():
        raise HTTPException(409, "蓝牙已断开，无法播放")
    ok = play_sound(payload.sound_id, 0, "manual", volume=payload.volume)
    return {"ok": ok}


# ===== 基线重置 =====
@router.post("/baseline/reset")
def reset_baseline():
    baseline.reset()
    return {"ok": True, "is_learning": True}


# ===== 历史数据 =====
@router.get("/history")
def history(range_: str = "day"):
    """range: day/week/month。返回事件、播放记录、聚合统计。"""
    now = datetime.now()
    if range_ == "week":
        start = now - timedelta(days=7)
    elif range_ == "month":
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=1)
    start_ts = start.isoformat()
    end_ts = now.isoformat()
    events = [dict(r) for r in database.get_noise_events(start_ts, end_ts)]
    playbacks = [dict(r) for r in database.get_playbacks(start_ts, end_ts)]
    db_samples = [dict(r) for r in database.get_db_samples(start_ts, end_ts)]

    # 按日聚合事件数
    daily = {}
    daily_peak = {}
    for e in events:
        day = e["ts"][:10]
        daily[day] = daily.get(day, 0) + 1
        daily_peak[day] = max(daily_peak.get(day, -100), e["peak_db"])

    # 按小时聚合（活动规律）
    hourly = [0] * 24
    for e in events:
        try:
            h = int(e["ts"][11:13])
            hourly[h] += 1
        except (ValueError, IndexError):
            pass

    # 等级分布
    level_dist = {1: 0, 2: 0, 3: 0}
    for e in events:
        lv = e["level_triggered"]
        if lv in level_dist:
            level_dist[lv] += 1

    # 分贝采样降采样（避免前端数据过大）
    if len(db_samples) > 500:
        step = len(db_samples) // 500
        db_samples = db_samples[::step][:500]

    return {
        "range": range_,
        "start": start_ts,
        "end": end_ts,
        "events": events,
        "playbacks": playbacks,
        "db_samples": db_samples,
        "daily": [{"day": k, "count": daily[k], "peak": round(daily_peak[k], 1)}
                  for k in sorted(daily)],
        "hourly": hourly,
        "level_dist": level_dist,
        "total_events": len(events),
        "total_playbacks": len(playbacks),
    }


# ===== 音频库 =====
@router.get("/sounds")
def list_sounds():
    rows = database.list_sounds()
    return [dict(r) for r in rows]


@router.delete("/sounds/{sid}")
def delete_sound(sid: str):
    row = database.get_sound(sid)
    if row is None:
        raise HTTPException(404, "音频不存在")
    # 内置音频不允许删除
    if row["type"] == "builtin":
        raise HTTPException(403, "内置音频不可删除")
    try:
        if os.path.exists(row["path"]):
            os.remove(row["path"])
    except OSError:
        pass
    database.delete_sound(sid)
    return {"ok": True}


# ===== 音频设备列表 =====
@router.get("/devices")
def devices():
    return {
        "input": capture.list_input_devices(),
        "output": capture.list_output_devices(),
    }


class SetInputPayload(BaseModel):
    device_index: int | None = None  # None=系统默认


@router.post("/devices/set-input")
def set_input_device(payload: SetInputPayload):
    """切换输入设备并重启采集。"""
    cfg = get_config()
    old = cfg["audio"]["input_device"]
    update_config({"audio": {"input_device": payload.device_index}})
    # 重启采集
    capture.stop()
    ok = capture.start()
    if not ok:
        # 回退
        update_config({"audio": {"input_device": old}})
        capture.start()
        raise HTTPException(500, "设备启动失败，已回退到原设备")
    return {"ok": True, "input_device": payload.device_index}


@router.post("/devices/test")
def test_input_device(payload: SetInputPayload):
    """测试指定设备录音2秒，返回信号强度。"""
    import sounddevice as sd
    idx = payload.device_index
    try:
        if idx is None:
            dev_info = sd.query_devices(kind="input")
            sr = int(dev_info["default_samplerate"]) if dev_info else 44100
        else:
            dev_info = sd.query_devices(idx)
            sr = int(dev_info.get("default_samplerate", 44100))
    except Exception as e:
        raise HTTPException(400, f"设备查询失败: {e}")
    try:
        dur = 2.0
        size = int(sr * dur)
        rec = sd.rec(size, samplerate=sr, channels=1, dtype="float32",
                     device=idx, blocking=True)
        if rec.size == 0:
            return {"ok": False, "error": "无数据"}
        rms = float(np.sqrt(np.mean(np.square(rec))))
        peak = float(np.max(np.abs(rec)))
        dbfs = 20 * np.log10(rms) if rms > 1e-10 else -100.0
        offset = get_config()["audio"]["calibration_offset"]
        spl = round(dbfs + offset, 2)
        if rms < 1e-6:
            strength = "无信号"
        elif rms < 1e-4:
            strength = "极弱"
        elif rms < 1e-2:
            strength = "正常"
        else:
            strength = "良好"
        return {
            "ok": True, "device_index": idx, "rms": rms, "peak": peak,
            "dbfs": round(dbfs, 2), "spl": spl, "strength": strength,
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ===== 声音绑定到等级 =====
class BindPayload(BaseModel):
    level: int      # 1/2/3
    sound_id: str


@router.post("/sounds/bind")
def bind_sound(payload: BindPayload):
    cfg = get_config()
    strat = dict(cfg["strategy"])
    key = f"l{payload.level}_sound"
    if key not in strat:
        raise HTTPException(400, "等级无效")
    strat[key] = payload.sound_id
    update_config({"strategy": strat})
    return {"ok": True, "strategy": strat}
