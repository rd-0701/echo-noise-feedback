"""检查各API的实际返回格式。"""
import json
import urllib.request

TOKEN = "fk8_gViRMN_H12ctG_mGRQ2JY0gMng1w"
BASE = "http://127.0.0.1:8000"
OUT = r"d:\桌面文件\echo-project\tunnel\api_formats.json"

def api(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": "Bearer " + TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return -1, {"error": str(e)}

result = {}
for path in ["/api/sounds", "/api/devices", "/api/status", "/api/config"]:
    s, d = api(path)
    # 只保存前500字符的结构
    txt = json.dumps(d, ensure_ascii=False)[:800]
    result[path] = {"status": s, "type": type(d).__name__, "preview": txt,
                    "keys": list(d.keys()) if isinstance(d, dict) else f"len={len(d)}"}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print("DONE:", OUT)
