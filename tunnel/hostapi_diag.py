"""深度诊断：列出所有 host API 及其设备，尝试在每个 API 下打开输入设备。"""
import sounddevice as sd
import numpy as np
import json

OUT = r"d:\桌面文件\echo-project\tunnel\hostapi_diag.json"

result = {"hostapis": [], "default_input": None, "test_results": []}

# 1. 列出所有 host API
try:
    hostapis = sd.query_hostapis()
    for i, api in enumerate(hostapis):
        result["hostapis"].append({
            "index": i,
            "name": api["name"],
            "devices": list(api["devices"]),
            "default_input_device": api.get("default_input_device"),
            "default_output_device": api.get("default_output_device"),
        })
except Exception as e:
    result["hostapis_error"] = str(e)

# 2. 系统默认输入
try:
    d = sd.query_devices(kind="input")
    result["default_input"] = {"name": d["name"], "hostapi": d["hostapi"],
                               "sr": d.get("default_samplerate"),
                               "channels": d["max_input_channels"]}
except Exception as e:
    result["default_input_error"] = str(e)

# 3. 对每个有输入通道的设备，打印完整信息并尝试录音
try:
    all_devs = sd.query_devices()
    for idx, dev in enumerate(all_devs):
        if dev.get("max_input_channels", 0) > 0:
            info = {
                "index": idx, "name": dev["name"],
                "hostapi": dev.get("hostapi"),
                "hostapi_name": sd.query_hostapis(dev["hostapi"])["name"] if dev.get("hostapi") is not None else "?",
                "max_input_channels": dev["max_input_channels"],
                "default_samplerate": dev.get("default_samplerate"),
                "default_low_input_latency": str(dev.get("default_low_input_latency")),
            }
            # 尝试用设备自己的默认采样率录音 1 秒
            sr = int(dev.get("default_samplerate", 44100))
            ch = min(dev["max_input_channels"], 1)
            try:
                size = int(sr * 1.0)
                rec = sd.rec(size, samplerate=sr, channels=1, dtype="float32",
                             device=idx, blocking=True)
                rms = float(np.sqrt(np.mean(np.square(rec)))) if rec.size > 0 else 0.0
                peak = float(np.max(np.abs(rec))) if rec.size > 0 else 0.0
                dbfs = 20 * np.log10(rms) if rms > 1e-10 else -100.0
                info["rms"] = rms
                info["peak"] = peak
                info["dbfs"] = round(dbfs, 2)
                info["spl"] = round(dbfs + 90.0, 2)
                info["has_signal"] = rms > 1e-4
                info["status"] = "OK"
            except Exception as e:
                info["status"] = f"FAIL: {type(e).__name__}: {e}"
            result["test_results"].append(info)
except Exception as e:
    result["scan_error"] = str(e)

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("DONE:", OUT)
