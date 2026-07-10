// 设置页：配置加载/保存
const Settings = {
  cfg: null,
  loaded: false,

  async load() {
    try {
      this.cfg = await API.getConfig();
      this._fill();
      this._loadDevices();
      this.loaded = true;
    } catch (e) { console.error(e); }
  },

  async _loadDevices() {
    try {
      const d = await API.devices();
      const sel = document.getElementById("cfg-input-device");
      if (!sel) return;
      const current = this.cfg.audio ? this.cfg.audio.input_device : null;
      // 保留"系统默认"选项
      sel.innerHTML = '<option value="">系统默认</option>';
      (d.input || []).forEach((dev) => {
        const opt = document.createElement("option");
        opt.value = dev.index;
        opt.textContent = `[${dev.index}] ${dev.name}`;
        if (current === dev.index) opt.selected = true;
        sel.appendChild(opt);
      });
    } catch (e) { console.error(e); }
  },

  _fill() {
    const c = this.cfg;
    const d = c.detection, s = c.strategy, sc = c.scheduler, sup = c.suppression;
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
    const chk = (id, v) => { const el = document.getElementById(id); if (el) el.checked = v; };
    set("cfg-threshold-offset", d.threshold_offset_db);
    set("cfg-abs-threshold", d.absolute_threshold_db);
    set("cfg-confirm-blocks", d.confirm_blocks);
    set("cfg-min-duration", d.min_duration_ms);
    chk("cfg-ignore-transient", d.ignore_transient);
    set("cfg-l1-delta", s.l1_delta_db);
    set("cfg-l2-delta", s.l2_delta_db);
    set("cfg-l1-dur", s.l1_duration_s);
    set("cfg-l2-dur", s.l2_duration_s);
    set("cfg-l3-dur", s.l3_duration_s);
    set("cfg-min-vol", s.min_volume);
    set("cfg-max-vol", s.max_volume);
    chk("cfg-sched-enabled", sc.enabled);
    set("cfg-sched-start", sc.start_time);
    set("cfg-sched-end", sc.end_time);
    set("cfg-sched-interval", sc.interval_minutes);
    set("cfg-sched-level", sc.level);
    set("cfg-cooldown", sup.cooldown_s);
  },

  init() {
    document.getElementById("save-config-btn").onclick = () => this.save();
    document.getElementById("baseline-reset-btn").onclick = async () => {
      try {
        await API.resetBaseline();
        const msg = document.getElementById("save-msg");
        msg.textContent = "已重新学习，需等1分钟";
        msg.style.color = "var(--accent)";
        setTimeout(() => { msg.textContent = ""; }, 3000);
      }
      catch (e) { alert(e.message); }
    };
    // 麦克风测试
    const testBtn = document.getElementById("mic-test-btn");
    if (testBtn) testBtn.onclick = () => this.testMic();
    // 应用麦克风
    const applyBtn = document.getElementById("apply-device-btn");
    if (applyBtn) applyBtn.onclick = () => this.applyDevice();
  },

  async testMic() {
    const sel = document.getElementById("cfg-input-device");
    const result = document.getElementById("mic-test-result");
    const btn = document.getElementById("mic-test-btn");
    const idx = sel.value === "" ? null : parseInt(sel.value, 10);
    btn.disabled = true;
    result.textContent = "录音中（2秒）...";
    result.className = "mic-test-result";
    try {
      const r = await API.testInputDevice(idx);
      if (r.ok) {
        const strengthText = { "无信号": "❌无信号", "极弱": "⚠️极弱", "正常": "✅正常", "良好": "✅良好" };
        result.textContent = `${strengthText[r.strength] || r.strength} — ${r.spl} dB（RMS=${r.rms.toExponential(2)}）`;
        result.className = "mic-test-result " + (r.strength === "无信号" || r.strength === "极弱" ? "bad" : "ok");
      } else {
        result.textContent = "❌ " + (r.error || "测试失败");
        result.className = "mic-test-result bad";
      }
    } catch (e) {
      result.textContent = "❌ " + e.message;
      result.className = "mic-test-result bad";
    }
    btn.disabled = false;
  },

  async applyDevice() {
    const sel = document.getElementById("cfg-input-device");
    const result = document.getElementById("mic-test-result");
    const btn = document.getElementById("apply-device-btn");
    const idx = sel.value === "" ? null : parseInt(sel.value, 10);
    btn.disabled = true;
    result.textContent = "切换中...";
    try {
      await API.setInputDevice(idx);
      result.textContent = "✅ 麦克风已切换";
      result.className = "mic-test-result ok";
    } catch (e) {
      result.textContent = "❌ " + e.message;
      result.className = "mic-test-result bad";
    }
    btn.disabled = false;
  },

  _collect() {
    const val = (id) => {
      const v = parseFloat(document.getElementById(id).value);
      return isNaN(v) ? undefined : v;
    };
    const ival = (id) => {
      const v = parseInt(document.getElementById(id).value, 10);
      return isNaN(v) ? undefined : v;
    };
    const chk = (id) => document.getElementById(id).checked;
    const cfg = {
      detection: {},
      strategy: {},
      scheduler: {},
      suppression: {},
    };
    const d = cfg.detection, s = cfg.strategy, sc = cfg.scheduler, sup = cfg.suppression;
    d.threshold_offset_db = val("cfg-threshold-offset");
    d.absolute_threshold_db = val("cfg-abs-threshold");
    d.confirm_blocks = ival("cfg-confirm-blocks");
    d.min_duration_ms = ival("cfg-min-duration");
    d.ignore_transient = chk("cfg-ignore-transient");
    s.l1_delta_db = val("cfg-l1-delta");
    s.l2_delta_db = val("cfg-l2-delta");
    s.l1_duration_s = val("cfg-l1-dur");
    s.l2_duration_s = val("cfg-l2-dur");
    s.l3_duration_s = val("cfg-l3-dur");
    s.min_volume = val("cfg-min-vol");
    s.max_volume = val("cfg-max-vol");
    sc.enabled = chk("cfg-sched-enabled");
    sc.start_time = document.getElementById("cfg-sched-start").value;
    sc.end_time = document.getElementById("cfg-sched-end").value;
    sc.interval_minutes = ival("cfg-sched-interval");
    sc.level = ival("cfg-sched-level");
    sup.cooldown_s = val("cfg-cooldown");
    // 移除 undefined 值，避免覆盖已有配置
    const clean = (obj) => {
      for (const k of Object.keys(obj)) {
        if (obj[k] === undefined) delete obj[k];
        else if (typeof obj[k] === "object") clean(obj[k]);
      }
    };
    clean(cfg);
    return cfg;
  },

  async save() {
    const msg = document.getElementById("save-msg");
    msg.textContent = "保存中...";
    msg.style.color = "var(--fg2)";
    try {
      this.cfg = await API.saveConfig(this._collect());
      msg.textContent = "已保存到电脑";
      msg.style.color = "var(--accent)";
      // 3秒后清除提示
      setTimeout(() => { msg.textContent = ""; }, 3000);
    } catch (e) {
      msg.textContent = "保存失败: " + e.message;
      msg.style.color = "var(--danger)";
    }
  },
};
