// 主应用：登录 / Tab 导航 / 初始化
const App = {
  async init() {
    // 登录
    const loginBtn = document.getElementById("login-btn");
    loginBtn.onclick = () => this.doLogin();
    document.getElementById("token-input").addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.doLogin();
    });

    // 支持 URL 参数自动登录（扫码进入）
    const urlToken = new URLSearchParams(location.search).get("token");
    if (urlToken) {
      API.setToken(urlToken);
      // 清除 URL 中的 token 参数，避免泄露
      const cleanUrl = location.pathname + location.hash;
      history.replaceState(null, "", cleanUrl);
    }

    if (!API.hasToken()) {
      this.showLogin();
      return;
    }
    this.start();
  },

  showLogin(msg) {
    document.getElementById("login-overlay").classList.remove("hidden");
    if (msg) document.getElementById("login-msg").textContent = msg;
    document.getElementById("token-input").focus();
  },

  async doLogin() {
    const t = document.getElementById("token-input").value.trim();
    if (!t) return;
    API.setToken(t);
    try {
      await API.status();
      document.getElementById("login-overlay").classList.add("hidden");
      this.start();
    } catch (e) {
      API.clearToken();
      this.showLogin("密码无效，请重试");
    }
  },

  onUnauthorized() {
    API.clearToken();
    WS.disconnect();
    this.showLogin("密码已失效，请重新输入");
  },

  async start() {
    // Tab 导航
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.onclick = () => this.switchView(tab.dataset.view);
    });
    // 总开关
    const toggle = document.getElementById("master-toggle");
    toggle.onchange = async () => {
      try { await API.toggle(toggle.checked); } catch (e) { toggle.checked = !toggle.checked; }
    };
    // 自动提醒开关
    const afToggle = document.getElementById("auto-feedback-toggle");
    afToggle.onchange = async () => {
      try { await API.setAutoFeedback(afToggle.checked); }
      catch (e) { afToggle.checked = !afToggle.checked; alert("设置失败: " + e.message); }
    };

    Dashboard.init();
    Settings.init();
    History.init();
    Workshop.init();

    WS.connect();
    // 定期拉状态（WS 断线兜底）
    this._statusTimer = setInterval(() => this.refreshStatus(), 5000);
    // 定期拉诊断（监控麦克风状态）
    this._diagTimer = setInterval(() => this.refreshDiagnostics(), 10000);
    await this.refreshStatus();
    await this.refreshDiagnostics();
  },

  async refreshStatus() {
    try {
      const s = await API.status();
      this.applyStatus(s);
      Dashboard.applyStatus(s);
    } catch (e) { /* 忽略，WS 仍在 */ }
  },

  async refreshDiagnostics() {
    try {
      const d = await API.diagnostics();
      this.applyDiagnostics(d);
    } catch (e) { /* 忽略 */ }
  },

  applyDiagnostics(d) {
    const warn = document.getElementById("mic-warning");
    const title = document.getElementById("mic-warning-title");
    const desc = document.getElementById("mic-warning-desc");
    if (!warn || !title || !desc) return;
    // 信号强度判定
    const strength = d.mic_signal_strength;
    if (d.block_count === 0) {
      warn.classList.remove("hidden", "ok");
      title.textContent = "麦克风未启动";
      desc.textContent = "音频采集未运行，请检查电脑端 Echo 服务是否正常。";
    } else if (strength === "无") {
      warn.classList.remove("hidden", "ok");
      title.textContent = "麦克风无信号";
      desc.textContent = "近5秒未检测到声音输入。请检查：①麦克风已连接 ②系统默认输入设备正确 ③麦克风音量不为0。" + (d.input_device === null ? "（当前使用系统默认输入）" : "");
    } else if (strength === "极弱") {
      warn.classList.remove("hidden", "ok");
      title.textContent = "麦克风信号极弱";
      desc.textContent = `当前分贝 ${d.current_db_spl} dB（估算），近5秒最高 ${d.recent_5s_db_spl_max} dB。可能麦克风离声源太远或音量过低。`;
    } else {
      // 信号正常 - 不显示警告
      warn.classList.add("hidden");
    }
  },

  applyStatus(s) {
    // 总开关
    document.getElementById("master-toggle").checked = s.enabled;
    // 自动提醒开关
    document.getElementById("auto-feedback-toggle").checked = s.auto_feedback;
    // 音响状态
    const bt = document.getElementById("bt-pill");
    bt.className = "pill " + (s.bt_connected ? "pill-ok" : "pill-bad");
    bt.textContent = s.bt_connected ? "音响●" : "音响断开";
    // 检测状态
    const st = document.getElementById("state-pill");
    if (!s.enabled) { st.className = "pill pill-bad"; st.textContent = "已关闭"; }
    else if (s.is_learning) { st.className = "pill pill-warn"; st.textContent = "学习中"; }
    else if (s.suppressed) { st.className = "pill pill-warn"; st.textContent = "冷却中"; }
    else { st.className = "pill pill-ok"; st.textContent = "运行中"; }
  },

  switchView(view) {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.view === view));
    document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === "view-" + view));
    if (view === "history") History.load();
    if (view === "workshop") Workshop.load();
    if (view === "settings") Settings.load();
  },
};

document.addEventListener("DOMContentLoaded", () => App.init());
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("/sw.js").catch(() => {}));
}
