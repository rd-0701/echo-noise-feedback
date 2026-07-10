"""全功能对抗式审查测试 - 直接写入文件结果。"""
import requests
import json
import time

REPORT = r"d:\桌面文件\echo-project\tunnel\test_result.txt"
_out = open(REPORT, "w", encoding="utf-8")

def log(msg=""):
    _out.write(str(msg) + "\n")
    _out.flush()

BASE = "http://127.0.0.1:8000"
TOKEN = "fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

passed = 0
failed = 0

def test(name, condition, detail=""):
    global passed, failed
    if condition:
        log(f"  [OK]   {name}")
        passed += 1
    else:
        log(f"  [FAIL] {name} {detail}")
        failed += 1

log("=" * 60)
log("  Echo 全功能对抗式审查")
log("=" * 60)

# 1. 健康检查
log("\n--- 1. 基础检查 ---")
try:
    r = requests.get(f"{BASE}/health", timeout=5)
    test("健康检查 200", r.status_code == 200, f"got {r.status_code}")
except Exception as e:
    test("健康检查", False, f"异常: {e}")

# 2. 未授权访问
try:
    r = requests.get(f"{BASE}/api/status", timeout=5)
    test("无Token返回401", r.status_code == 401, f"got {r.status_code}")
except Exception as e:
    test("无Token访问", False, f"异常: {e}")

# 3. 状态API（含auto_feedback）
log("\n--- 2. 状态API ---")
r = requests.get(f"{BASE}/api/status", headers=HEADERS, timeout=5)
test("状态API 200", r.status_code == 200)
s = r.json()
test("包含 auto_feedback 字段", "auto_feedback" in s, f"keys: {list(s.keys())}")
test("auto_feedback 默认 True", s.get("auto_feedback") == True, f"got {s.get('auto_feedback')}")
log(f"  状态: enabled={s.get('enabled')}, auto_fb={s.get('auto_feedback')}, "
    f"db={s.get('current_db')}, threshold={s.get('threshold')}, learning={s.get('is_learning')}")

# 4. 自动反馈开关
log("\n--- 3. 自动反馈开关 ---")
r = requests.post(f"{BASE}/api/auto-feedback", headers=HEADERS,
                  json={"auto_feedback": False}, timeout=5)
test("关闭自动反馈", r.status_code == 200 and r.json().get("auto_feedback") == False,
     f"status={r.status_code}, body={r.text}")
r = requests.get(f"{BASE}/api/status", headers=HEADERS, timeout=5)
test("状态反映关闭", r.json().get("auto_feedback") == False)
r = requests.post(f"{BASE}/api/auto-feedback", headers=HEADERS,
                  json={"auto_feedback": True}, timeout=5)
test("开启自动反馈", r.status_code == 200 and r.json().get("auto_feedback") == True)
r = requests.get(f"{BASE}/api/status", headers=HEADERS, timeout=5)
test("状态反映开启", r.json().get("auto_feedback") == True)

# 5. 配置保存/读取
log("\n--- 4. 配置持久化 ---")
r = requests.get(f"{BASE}/api/config", headers=HEADERS, timeout=5)
cfg = r.json()
test("读取配置 200", r.status_code == 200)
test("配置包含 auto_feedback", "auto_feedback" in cfg, f"keys: {list(cfg.keys())}")
test("配置包含新的alert音", cfg["strategy"]["l1_sound"] == "alert_beep",
     f"l1_sound={cfg['strategy']['l1_sound']}")
log(f"  声音绑定: L1={cfg['strategy']['l1_sound']}, "
    f"L2={cfg['strategy']['l2_sound']}, L3={cfg['strategy']['l3_sound']}")

# 修改并保存
new_offset = cfg["detection"]["threshold_offset_db"]
r = requests.put(f"{BASE}/api/config", headers=HEADERS,
                 json={"config": {"detection": {"threshold_offset_db": 20.0}}}, timeout=5)
test("保存配置 200", r.status_code == 200, f"status={r.status_code}, body={r.text[:200]}")
saved = r.json()
test("保存后阈值偏移=20", saved["detection"]["threshold_offset_db"] == 20.0,
     f"got {saved['detection']['threshold_offset_db']}")
# 恢复
requests.put(f"{BASE}/api/config", headers=HEADERS,
             json={"config": {"detection": {"threshold_offset_db": new_offset}}}, timeout=5)

# 6. 音频库
log("\n--- 5. 音频库 ---")
r = requests.get(f"{BASE}/api/sounds", headers=HEADERS, timeout=5)
sounds = r.json()
test("音频库 200", r.status_code == 200)
sound_ids = [s["id"] for s in sounds]
log(f"  音频列表 ({len(sounds)} 个): {sound_ids}")
test("包含 alert_beep", "alert_beep" in sound_ids)
test("包含 alert_siren", "alert_siren" in sound_ids)
test("包含 alert_buzzer", "alert_buzzer" in sound_ids)
test("包含 alert_chime", "alert_chime" in sound_ids)
test("包含原有 l1_hum", "l1_hum" in sound_ids)

# 7. 历史API（含db_samples）
log("\n--- 6. 历史数据 ---")
r = requests.get(f"{BASE}/api/history?range_=day", headers=HEADERS, timeout=5)
test("历史API 200", r.status_code == 200)
h = r.json()
test("包含 db_samples 字段", "db_samples" in h, f"keys: {list(h.keys())}")
test("包含 events 字段", "events" in h)
test("包含 playbacks 字段", "playbacks" in h)
test("包含 daily 字段", "daily" in h)
test("包含 hourly 字段", "hourly" in h)
test("包含 level_dist 字段", "level_dist" in h)
log(f"  事件数: {h.get('total_events')}, 播放数: {h.get('total_playbacks')}, "
    f"采样数: {len(h.get('db_samples', []))}")

# 等待几秒让db_samples积累
log("\n  等待10秒收集分贝采样...")
time.sleep(10)
r = requests.get(f"{BASE}/api/history?range_=day", headers=HEADERS, timeout=5)
h = r.json()
samples = h.get("db_samples", [])
test("10秒后有采样数据", len(samples) > 0, f"got {len(samples)} samples")
if samples:
    log(f"  最新采样: db={samples[-1]['db']}, threshold={samples[-1]['threshold']}")

# 8. URL参数Token认证
log("\n--- 7. URL参数Token ---")
r = requests.get(f"{BASE}/api/status?token={TOKEN}", timeout=5)
test("query参数Token认证", r.status_code == 200)

r = requests.get(f"{BASE}/api/status?token=wrong", timeout=5)
test("错误query参数Token", r.status_code == 401)

# 9. 数据库文件检查
log("\n--- 8. 数据持久化文件检查 ---")
import os
data_dir = r"d:\桌面文件\echo-project\data"
config_path = os.path.join(data_dir, "config.json")
db_path = os.path.join(data_dir, "echo.db")
token_path = os.path.join(data_dir, "auth_token.txt")

test("config.json 存在", os.path.exists(config_path))
test("echo.db 存在", os.path.exists(db_path))
test("auth_token.txt 存在", os.path.exists(token_path))

if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        saved_cfg = json.load(f)
    test("config.json 包含 auto_feedback", "auto_feedback" in saved_cfg)
    test("config.json auto_feedback=true", saved_cfg.get("auto_feedback") == True)
    log(f"  config.json: auto_feedback={saved_cfg.get('auto_feedback')}, "
        f"l1={saved_cfg['strategy']['l1_sound']}")

if os.path.exists(db_path):
    db_size = os.path.getsize(db_path)
    test("echo.db 非空", db_size > 0, f"size={db_size}")
    log(f"  echo.db 大小: {db_size} 字节")

# 10. 总结
log("\n" + "=" * 60)
log(f"  结果: {passed} 通过, {failed} 失败")
if failed == 0:
    log("  *** 全部通过 ***")
log("=" * 60)

_out.close()
print("Done. Report at:", REPORT)
