"""快速检查服务器是否在运行 + 拉取诊断信息。结果写到文件，避免终端崩溃。"""
import json
import urllib.request

TOKEN = "fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w"
OUT = r"d:\桌面文件\echo-project\tunnel\quick_check_result.json"

result = {"server_reachable": False, "diagnostics": None, "error": None}
try:
    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/diagnostics",
        headers={"Authorization": "Bearer " + TOKEN},
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        data = r.read().decode("utf-8")
        result["server_reachable"] = True
        result["diagnostics"] = json.loads(data)
except Exception as e:
    result["error"] = f"{type(e).__name__}: {e}"

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print("RESULT_FILE:", OUT)
print("REACHABLE:", result["server_reachable"])
if result["error"]:
    print("ERROR:", result["error"])
