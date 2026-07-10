// 仪表盘：实时分贝表 / 事件日志 / 手动触发
const Dashboard = {
  events: [],
  init() {
    // 手动触发
    document.querySelectorAll(".btn-trig").forEach((btn) => {
      btn.onclick = async () => {
        const level = parseInt(btn.dataset.level, 10);
        btn.disabled = true;
        try { await API.trigger(level); } catch (e) { alert(e.message); }
        setTimeout(() => btn.disabled = false, 1000);
      };
    });

    // WebSocket 订阅
    WS.on("db", (m) => this.updateGauge(m));
    WS.on("event", (m) => this.addEvent(m));
    WS.on("playback", (m) => this.addPlayback(m));
    WS.on("bt_status", (m) => {
      const bt = document.getElementById("bt-pill");
      bt.className = "pill " + (m.connected ? "pill-ok" : "pill-bad");
      bt.textContent = m.connected ? "音响●" : "音响断开";
    });
    WS.on("alert", (m) => {
      this.addSystemLine(m.msg || "");
    });
  },

  applyStatus(s) {
    this.updateGauge({
      value: s.current_db,
      baseline: s.baseline || 0,
      threshold: s.threshold,
    });
  },

  updateGauge(m) {
    const db = m.value;
    // SPL 单位（0-120），负值视为无效
    document.getElementById("db-value").textContent = db > 0 ? db.toFixed(1) : "--";
    const baseline = m.baseline || 0;
    const threshold = m.threshold || 40;
    document.getElementById("baseline-val").textContent = baseline > 0 ? baseline.toFixed(1) : "--";
    document.getElementById("threshold-val").textContent = threshold.toFixed(1);
    // 比例：0-80dB SPL 映射到 0-100%
    const pct = Math.max(0, Math.min(100, (db / 80) * 100));
    document.getElementById("db-fill").style.width = pct + "%";
    const markPct = Math.max(0, Math.min(100, (threshold / 80) * 100));
    document.getElementById("threshold-mark").style.left = markPct + "%";
  },

  addEvent(m) {
    const li = document.createElement("li");
    const lvl = m.level || 0;
    li.className = "lvl-" + lvl;
    const time = new Date(m.ts).toLocaleTimeString("zh-CN", { hour12: false });
    const lvlNames = { 1: "轻提醒", 2: "中警告", 3: "强干预" };
    const desc = m.triggered ? `触发${lvlNames[lvl] || "L" + lvl}` : "未触发";
    li.innerHTML = `<span>${desc} · 均${m.avg_db}dB<span class="ev-time">${time}</span></span>` +
                   `<span class="ev-db">峰值${m.peak_db}dB</span>`;
    this._prepend(li);
  },

  addPlayback(m) {
    const li = document.createElement("li");
    li.className = "lvl-" + m.level;
    const time = new Date(m.ts).toLocaleTimeString("zh-CN", { hour12: false });
    const lvlNames = { 1: "轻提醒", 2: "中警告", 3: "强干预" };
    const srcMap = { noise: "自动", scheduled: "定时", manual: "手动" };
    li.innerHTML = `<span>播放${lvlNames[m.level] || ""} · ${srcMap[m.source] || m.source}<span class="ev-time">${time}</span></span>` +
                   `<span class="ev-db">音量${Math.round(m.volume * 100)}%</span>`;
    this._prepend(li);
  },

  addSystemLine(msg) {
    const li = document.createElement("li");
    li.className = "lvl-0";
    const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    li.innerHTML = `<span><span class="sys-msg"></span><span class="ev-time">${time}</span></span><span></span>`;
    li.querySelector(".sys-msg").textContent = msg;
    this._prepend(li);
  },

  _prepend(li) {
    const log = document.getElementById("event-log");
    log.insertBefore(li, log.firstChild);
    while (log.children.length > 30) log.removeChild(log.lastChild);
  },
};
