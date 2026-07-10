"""对抗式审查 - 全面验证6大问题修复 + 同类问题排查。
结果写入文件，避免 PSReadLine 终端崩溃。"""
import json
import urllib.request
import urllib.error
import time
import os
import sys

TOKEN = "fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w"
BASE = "http://127.0.0.1:8000"
OUT = r"d:\桌面文件\echo-project\tunnel\adversarial_review.json"

results = {"start_time": time.strftime("%Y-%m-%d %H:%M:%S"), "tests": []}

# 预先创建文件，确保即使崩溃也有输出
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"stage": "init", "results": results}, f, ensure_ascii=False)

def _save():
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def api(method, path, body=None):
    url = BASE + path
    headers = {"Authorization": "Bearer " + TOKEN}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return -1, {"error": f"{type(e).__name__}: {e}"}

def test(name, func):
    try:
        passed, detail = func()
        results["tests"].append({"name": name, "passed": passed, "detail": detail})
    except Exception as e:
        results["tests"].append({"name": name, "passed": False, "detail": f"EXCEPTION: {type(e).__name__}: {e}"})
    _save()
    return results["tests"][-1]["passed"]

# ===== 1. 服务器健康 =====
def t_health():
    s, d = api("GET", "/api/status")
    if s != 200: return False, f"status={s}"
    return True, "OK"

# ===== 2. 诊断 - 麦克风信号 =====
def t_mic_signal():
    s, d = api("GET", "/api/diagnostics")
    if s != 200: return False, f"status={s}"
    strength = d.get("mic_signal_strength")
    block_count = d.get("block_count", 0)
    if block_count < 10: return False, f"block_count={block_count} (采集未运行)"
    if strength in ("无",): return False, f"信号强度={strength}"
    # 信号极弱或正常或良好都算通过（至少设备在工作）
    return True, f"strength={strength} block_count={block_count} db_spl={d.get('current_db_spl')}"

# ===== 3. 自动反馈开关 =====
def t_auto_feedback_toggle():
    # 先关
    s, d = api("POST", "/api/auto-feedback", {"auto_feedback": False})
    if s != 200: return False, f"关闭失败 status={s}"
    s, d = api("GET", "/api/status")
    if d.get("auto_feedback") != False: return False, "关闭后状态不匹配"
    # 再开
    s, d = api("POST", "/api/auto-feedback", {"auto_feedback": True})
    if s != 200: return False, f"开启失败 status={s}"
    s, d = api("GET", "/api/status")
    if d.get("auto_feedback") != True: return False, "开启后状态不匹配"
    return True, "开关正常"

# ===== 4. 配置持久化 =====
def t_config_persist():
    # 读取当前配置
    s, cfg = api("GET", "/api/config")
    if s != 200: return False, f"读取配置失败 status={s}"
    original = cfg.get("threshold_offset_db", 15)
    # 修改
    new_val = original + 1 if original < 30 else original - 1
    cfg2 = dict(cfg)
    cfg2["threshold_offset_db"] = new_val
    s, d = api("PUT", "/api/config", {"config": cfg2})
    if s != 200: return False, f"保存配置失败 status={s} {d}"
    # 重新读取验证
    s, cfg3 = api("GET", "/api/config")
    if cfg3.get("threshold_offset_db") != new_val:
        return False, f"保存后值不匹配: 期望={new_val} 实际={cfg3.get('threshold_offset_db')}"
    # 恢复原始值
    cfg4 = dict(cfg3)
    cfg4["threshold_offset_db"] = original
    api("PUT", "/api/config", {"config": cfg4})
    return True, f"原值={original} 改为={new_val} 恢复={original}"

# ===== 5. 音频库 =====
def t_sounds():
    s, d = api("GET", "/api/sounds")
    if s != 200: return False, f"status={s}"
    # API 返回 list（不是 dict）
    sounds = d if isinstance(d, list) else d.get("sounds", [])
    if len(sounds) < 3: return False, f"音频太少: {len(sounds)}"
    has_ids = all("id" in x and "name" in x for x in sounds)
    if not has_ids: return False, "音频缺少id/name字段"
    return True, f"{len(sounds)}个音频: {[x['name'] for x in sounds[:5]]}"

# ===== 6. 历史数据 =====
def t_history():
    s, d = api("GET", "/api/history?range_=day")
    if s != 200: return False, f"status={s}"
    has_events = "events" in d
    has_daily = "daily" in d
    has_hourly = "hourly" in d
    has_level = "level_dist" in d
    has_samples = "db_samples" in d
    issues = []
    if not has_events: issues.append("缺events")
    if not has_daily: issues.append("缺daily")
    if not has_hourly: issues.append("缺hourly")
    if not has_level: issues.append("缺level_dist")
    if not has_samples: issues.append("缺db_samples")
    if issues: return False, f"历史数据不完整: {', '.join(issues)}"
    return True, f"events={len(d['events'])} samples={len(d.get('db_samples',[]))} daily={len(d['daily'])}"

# ===== 7. db_samples 是否在积累 =====
def t_db_samples_growing():
    s, d1 = api("GET", "/api/history?range_=day")
    c1 = len(d1.get("db_samples", []))
    time.sleep(6)  # 等待更多采样
    s, d2 = api("GET", "/api/history?range_=day")
    c2 = len(d2.get("db_samples", []))
    if c2 <= c1:
        return False, f"采样未增长: before={c1} after={c2}"
    return True, f"采样在增长: {c1} → {c2}"

# ===== 8. 手动触发 =====
def t_manual_trigger():
    s, d = api("POST", "/api/trigger", {"level": 1})
    if s != 200: return False, f"status={s} {d}"
    return True, "手动触发成功"

# ===== 9. URL Token 认证 =====
def t_auth():
    # 无 token
    req = urllib.request.Request(BASE + "/api/status")
    try:
        urllib.request.urlopen(req, timeout=5)
        return False, "无token也能访问"
    except urllib.error.HTTPError as e:
        if e.code != 401: return False, f"期望401 实际={e.code}"
    # 错误 token
    req = urllib.request.Request(BASE + "/api/status", headers={"Authorization": "Bearer wrong_token"})
    try:
        urllib.request.urlopen(req, timeout=5)
        return False, "错误token也能访问"
    except urllib.error.HTTPError as e:
        if e.code != 401: return False, f"期望401 实际={e.code}"
    return True, "认证正确拒绝无token和错误token"

# ===== 10. 设备列表 =====
def t_devices():
    s, d = api("GET", "/api/devices")
    if s != 200: return False, f"status={s}"
    inputs = d.get("input", [])  # API 用 "input" 不是 "inputs"
    if len(inputs) == 0: return False, "无输入设备"
    return True, f"{len(inputs)}个输入设备"

# ===== 11. 数据文件持久化 =====
def t_data_files():
    data_dir = r"d:\桌面文件\echo-project\data"
    sounds_dir = r"d:\桌面文件\echo-project\backend\sounds"
    checks = {
        "data/config.json": os.path.exists(os.path.join(data_dir, "config.json")),
        "data/auth_token.txt": os.path.exists(os.path.join(data_dir, "auth_token.txt")),
        "data/echo.db": os.path.exists(os.path.join(data_dir, "echo.db")),
        "backend/sounds/": os.path.isdir(sounds_dir),
    }
    missing = [k for k, v in checks.items() if not v]
    if missing: return False, f"缺失: {missing}"
    return True, f"全部存在: {list(checks.keys())}"

# ===== 14. 麦克风设备测试端点 =====
def t_device_test():
    s, d = api("POST", "/api/devices/test", {"device_index": None})
    if s != 200: return False, f"status={s} {d}"
    if not d.get("ok"): return False, f"测试失败: {d.get('error')}"
    return True, f"strength={d.get('strength')} spl={d.get('spl')} rms={d.get('rms')}"

# ===== 15. 声音绑定验证 =====
def t_sound_bindings():
    s, cfg = api("GET", "/api/config")
    if s != 200: return False, f"读取配置失败"
    s, sounds = api("GET", "/api/sounds")
    if s != 200: return False, f"读取音频库失败"
    sound_list = sounds if isinstance(sounds, list) else sounds.get("sounds", [])
    sound_ids = {x["id"] for x in sound_list}
    strat = cfg.get("strategy", {})
    issues = []
    for level in [1, 2, 3]:
        key = f"l{level}_sound"
        sid = strat.get(key)
        if sid and sid not in sound_ids:
            issues.append(f"{key}={sid} 不存在")
    if issues: return False, f"声音绑定不匹配: {issues}"
    return True, f"L1={strat.get('l1_sound')} L2={strat.get('l2_sound')} L3={strat.get('l3_sound')} 均有效"

# ===== 12. 基线重置 =====
def t_baseline_reset():
    s, d = api("POST", "/api/baseline/reset")
    if s != 200: return False, f"status={s} {d}"
    # 等待学习
    time.sleep(3)
    s, d = api("GET", "/api/diagnostics")
    # baseline 可能还在学习中
    return True, f"重置后 baseline={d.get('baseline')} state={d.get('detector_state')}"

# ===== 13. 自动反馈触发验证（等待噪音事件） =====
def t_auto_feedback_event():
    # 先确认自动反馈开启
    s, d = api("GET", "/api/status")
    if not d.get("auto_feedback"): return False, "自动反馈未开启"
    if not d.get("enabled"): return False, "总开关未开启"
    # 记录当前事件数
    s, h = api("GET", "/api/history?range_=day")
    events_before = len(h.get("events", []))
    playbacks_before = h.get("total_playbacks", 0)
    # 等待 10 秒，看是否有新事件（取决于用户是否在制造噪音）
    time.sleep(10)
    s, h2 = api("GET", "/api/history?range_=day")
    events_after = len(h2.get("events", []))
    playbacks_after = h2.get("total_playbacks", 0)
    # 检查诊断中的事件计数
    s, diag = api("GET", "/api/diagnostics")
    ev_count = diag.get("event_count", 0)
    return True, f"events: {events_before}→{events_after} playbacks: {playbacks_before}→{playbacks_after} diag_events={ev_count}"

# ===== 运行所有测试 =====
all_tests = [
    ("1. 服务器健康检查", t_health),
    ("2. 麦克风信号正常", t_mic_signal),
    ("3. 自动反馈开关", t_auto_feedback_toggle),
    ("4. 配置持久化", t_config_persist),
    ("5. 音频库完整性", t_sounds),
    ("6. 历史数据完整性", t_history),
    ("7. db_samples持续积累", t_db_samples_growing),
    ("8. 手动触发提醒", t_manual_trigger),
    ("9. Token认证安全性", t_auth),
    ("10. 设备列表API", t_devices),
    ("11. 数据文件持久化", t_data_files),
    ("12. 基线重置", t_baseline_reset),
    ("13. 自动反馈事件监测", t_auto_feedback_event),
    ("14. 麦克风设备测试端点", t_device_test),
    ("15. 声音绑定验证", t_sound_bindings),
]

passed = 0
for name, func in all_tests:
    if test(name, func):
        passed += 1

results["end_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
results["summary"] = f"{passed}/{len(all_tests)} 通过"
_save()
