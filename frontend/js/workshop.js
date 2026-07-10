// 声音管理：音频库 / 试听 / 绑定 / 上传 / 录制 / 合成 / EQ
const Workshop = {
  sounds: [],
  selectedId: null,
  boundSounds: {},  // {level: sound_id}

  async load() {
    try {
      this.sounds = await API.listSounds();
      const cfg = await API.getConfig();
      this.boundSounds = {
        1: cfg.strategy.l1_sound,
        2: cfg.strategy.l2_sound,
        3: cfg.strategy.l3_sound,
      };
      this._render();
    } catch (e) { console.error(e); }
  },

  init() {
    document.getElementById("upload-btn").onclick = () => this.upload();
    document.getElementById("record-btn").onclick = () => this.record();
    document.getElementById("synth-btn").onclick = () => this.synthesize();
    document.getElementById("eq-btn").onclick = () => this.equalize();
  },

  _render() {
    const list = document.getElementById("sound-list");
    list.innerHTML = "";
    this.sounds.forEach((s) => {
      const li = document.createElement("li");
      li.dataset.id = s.id;
      if (s.id === this.selectedId) li.style.borderColor = "#4ade80";
      const isBuiltin = s.type === "builtin";
      // 检查是否已绑定到某个等级
      const boundLevels = [];
      for (const [lv, sid] of Object.entries(this.boundSounds)) {
        if (sid === s.id) boundLevels.push(lv);
      }
      const boundBadge = boundLevels.length > 0
        ? `<span class="snd-bound">已用于${boundLevels.map(l => ["","轻","中","强"][l]).join("+")}</span>`
        : "";
      // 使用 textContent 防止 XSS（s.name 来自用户输入）
      li.innerHTML = `
        <span><span class="snd-name"></span><span class="snd-type">[${s.type === "builtin" ? "内置" : "自定义"}]</span>${boundBadge}</span>
        <span class="snd-actions">
          <button class="prev">试听</button>
          <button class="bind-btn b1" title="设为轻提醒">轻</button>
          <button class="bind-btn b2" title="设为中警告">中</button>
          <button class="bind-btn b3" title="设为强干预">强</button>
          ${isBuiltin ? "" : '<button class="del">删</button>'}
        </span>`;
      // 安全设置用户输入的名称
      li.querySelector(".snd-name").textContent = s.name;
      li.querySelector(".prev").onclick = () => this.preview(s.id);
      li.querySelector(".b1").onclick = () => this.bind(1, s.id);
      li.querySelector(".b2").onclick = () => this.bind(2, s.id);
      li.querySelector(".b3").onclick = () => this.bind(3, s.id);
      const del = li.querySelector(".del");
      if (del) del.onclick = () => this.del(s.id);
      li.onclick = (e) => {
        if (e.target.tagName === "BUTTON") return;
        this.selectedId = s.id; this._render();
      };
      list.appendChild(li);
    });
  },

  async preview(id) {
    try { await API.preview(id, 0.8); this._msg("播放中..."); }
    catch (e) { alert(e.message); }
  },

  async bind(level, id) {
    const names = { 1: "轻提醒", 2: "中警告", 3: "强干预" };
    try {
      await API.bindSound(level, id);
      this.boundSounds[level] = id;
      this._msg(`已设为「${names[level]}」提醒音`);
      this._render();
    }
    catch (e) { alert(e.message); }
  },

  async del(id) {
    if (!confirm("删除该音频？")) return;
    try { await API.deleteSound(id); if (this.selectedId === id) this.selectedId = null; this.load(); }
    catch (e) { alert(e.message); }
  },

  async upload() {
    const f = document.getElementById("upload-file").files[0];
    if (!f) { this._msg("请先选择文件"); return; }
    this._msg("上传中...");
    try { await API.upload(f); this._msg("上传成功"); this.load(); }
    catch (e) { this._msg("失败: " + e.message); }
  },

  async record() {
    const sec = parseInt(document.getElementById("record-seconds").value, 10) || 5;
    this._msg("录制中...");
    try { await API.record(sec); this._msg(`录制请求已发送（${sec}s）`); setTimeout(() => this.load(), sec * 1000 + 500); }
    catch (e) { this._msg("失败: " + e.message); }
  },

  async synthesize() {
    const p = {
      name: document.getElementById("synth-name").value || "合成音",
      kind: document.getElementById("synth-kind").value,
      f0: parseFloat(document.getElementById("synth-f0").value),
      f1: parseFloat(document.getElementById("synth-f1").value),
      duration_s: parseFloat(document.getElementById("synth-dur").value),
    };
    this._msg("合成中...");
    try { await API.synthesize(p); this._msg("合成完成"); this.load(); }
    catch (e) { this._msg("失败: " + e.message); }
  },

  async equalize() {
    if (!this.selectedId) { this._msg("请先点选一个音频"); return; }
    const text = document.getElementById("eq-bands").value.trim();
    if (!text) { this._msg("请填写频段"); return; }
    const bands = [];
    for (const line of text.split("\n")) {
      const parts = line.split(/[,\s]+/).filter(Boolean);
      if (parts.length >= 3) {
        bands.push({ freq_low: parseFloat(parts[0]), freq_high: parseFloat(parts[1]), gain_db: parseFloat(parts[2]) });
      }
    }
    if (!bands.length) { this._msg("频段格式错误"); return; }
    this._msg("处理中...");
    try { await API.equalize(this.selectedId, bands); this._msg("EQ 完成，已生成新音频"); this.load(); }
    catch (e) { this._msg("失败: " + e.message); }
  },

  _msg(t) { document.getElementById("workshop-msg").textContent = t; },
};
