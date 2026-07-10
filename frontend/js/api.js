// API 客户端：Token 认证 + REST 调用
const API = {
  token: localStorage.getItem("echo_token") || "",

  setToken(t) { this.token = t; localStorage.setItem("echo_token", t); },
  hasToken() { return !!this.token; },
  clearToken() { this.token = ""; localStorage.removeItem("echo_token"); },

  async request(method, path, body, isForm) {
    const opts = { method, headers: { Authorization: "Bearer " + this.token } };
    if (body !== undefined && body !== null) {
      if (isForm) { opts.body = body; }
      else { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    }
    const res = await fetch(path, opts);
    if (res.status === 401) { App.onUnauthorized(); throw new Error("未授权"); }
    if (!res.ok) {
      let msg = res.status;
      try { msg = (await res.json()).detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    return res.json();
  },

  // 状态
  status() { return this.request("GET", "/api/status"); },
  // 诊断
  diagnostics() { return this.request("GET", "/api/diagnostics"); },
  // 配置
  getConfig() { return this.request("GET", "/api/config"); },
  saveConfig(config) { return this.request("PUT", "/api/config", { config }); },
  toggle(enabled) { return this.request("POST", "/api/toggle", { enabled }); },
  setAutoFeedback(on) { return this.request("POST", "/api/auto-feedback", { auto_feedback: on }); },
  // 触发
  trigger(level) { return this.request("POST", "/api/trigger", { level }); },
  preview(soundId, volume) { return this.request("POST", "/api/preview", { sound_id: soundId, volume }); },
  resetBaseline() { return this.request("POST", "/api/baseline/reset"); },
  // 历史
  history(range) { return this.request("GET", `/api/history?range_=${range}`); },
  // 音频
  listSounds() { return this.request("GET", "/api/sounds"); },
  deleteSound(id) { return this.request("DELETE", "/api/sounds/" + id); },
  bindSound(level, soundId) { return this.request("POST", "/api/sounds/bind", { level, sound_id: soundId }); },
  // 工坊
  upload(file) {
    const fd = new FormData(); fd.append("file", file);
    return this.request("POST", "/api/sounds/upload", fd, true);
  },
  record(seconds) { return this.request("POST", "/api/sounds/record", { seconds }); },
  synthesize(p) { return this.request("POST", "/api/sounds/synthesize", p); },
  equalize(id, bands) { return this.request("POST", `/api/sounds/${id}/equalize`, { bands }); },
  // 设备
  devices() { return this.request("GET", "/api/devices"); },
  setInputDevice(deviceIndex) { return this.request("POST", "/api/devices/set-input", { device_index: deviceIndex }); },
  testInputDevice(deviceIndex) { return this.request("POST", "/api/devices/test", { device_index: deviceIndex }); },
};
