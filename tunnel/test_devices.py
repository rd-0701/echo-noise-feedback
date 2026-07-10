"""测试每个输入设备的实际信号强度。逐设备写入结果，确保即使崩溃也有部分数据。"""
import sounddevice as sd
import numpy as np
import time
import json
import sys
import traceback

OUT = r"d:\桌面文件\echo-project\tunnel\device_test_result.json"
ERR = r"d:\桌面文件\echo-project\tunnel\device_test_err.txt"

_err_lines = []
def _log_err(s):
    _err_lines.append(s)
    with open(ERR, "w", encoding="utf-8") as f:
        f.write("\n".join(_err_lines))

results = []
try:
    devs = sd.query_devices()
except Exception as e:
    _log_err(f"query_devices 失败: {e}")
    devs = []

input_devs = [(i, d) for i, d in enumerate(devs) if d.get("max_input_channels", 0) > 0]

# 先写入设备列表
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"stage": "list", "input_devices": [
        {"index": i, "name": d["name"], "sr": d.get("default_samplerate", 44100)}
        for i, d in input_devs
    ]}, f, ensure_ascii=False, indent=2)

for idx, d in input_devs:
    name = d["name"]
    sr = int(d.get("default_samplerate", 44100))
    entry = {"index": idx, "name": name, "sr": sr, "rms": None, "peak": None,
             "dbfs": None, "spl": None, "has_signal": False, "error": None}
    try:
        dur = 1.5
        size = int(sr * dur)
        rec = sd.rec(size, samplerate=sr, channels=1, dtype="float32",
                     device=idx, blocking=True)
        if rec.size > 0:
            rms = float(np.sqrt(np.mean(np.square(rec))))
            peak = float(np.max(np.abs(rec))) if rec.size > 0 else 0.0
            dbfs = 20 * np.log10(rms) if rms > 1e-10 else -100.0
            spl = dbfs + 90.0
            entry.update({"rms": rms, "peak": peak, "dbfs": round(dbfs, 2),
                          "spl": round(spl, 2), "has_signal": rms > 1e-4})
    except Exception as e:
        entry["error"] = f"{type(e).__name__}: {e}"
        _log_err(f"[idx={idx} {name}] {e}")

    results.append(entry)
    # 每测完一个设备就写一次文件
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"stage": "progress", "results": results}, f, ensure_ascii=False, indent=2)
    time.sleep(0.2)

# 最终结果
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"stage": "done", "results": results}, f, ensure_ascii=False, indent=2)
_log_err("DONE")
