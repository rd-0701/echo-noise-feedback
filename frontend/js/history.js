// 历史分析：Chart.js 图表 + 事件列表
const History = {
  charts: {},
  range: "day",

  init() {
    document.querySelectorAll(".range-btn").forEach((btn) => {
      btn.onclick = () => {
        document.querySelectorAll(".range-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        this.range = btn.dataset.range;
        this.load();
      };
    });
  },

  async load() {
    if (typeof Chart === "undefined") {
      setTimeout(() => this.load(), 500);
      return;
    }
    try {
      const data = await API.history(this.range);
      this._renderStats(data);
      this._renderDb(data);
      this._renderDaily(data);
      this._renderHourly(data);
      this._renderLevel(data);
      this._renderEventList(data);
    } catch (e) { console.error(e); }
  },

  _renderStats(data) {
    document.getElementById("stat-events").textContent = data.total_events;
    document.getElementById("stat-playbacks").textContent = data.total_playbacks;
    let peak = null;
    data.events.forEach((e) => { if (peak === null || e.peak_db > peak) peak = e.peak_db; });
    document.getElementById("stat-peak").textContent = peak !== null ? peak.toFixed(1) : "--";
  },

  _destroy(key) { if (this.charts[key]) { this.charts[key].destroy(); delete this.charts[key]; } },

  _commonOpts() {
    return {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: "#9ca3af", font: { size: 11 } } } },
      scales: {
        x: { ticks: { color: "#9ca3af", font: { size: 10 } }, grid: { color: "#2d3540" } },
        y: { ticks: { color: "#9ca3af", font: { size: 10 } }, grid: { color: "#2d3540" } },
      },
    };
  },

  _renderDb(data) {
    this._destroy("db");
    const ctx = document.getElementById("chart-db");
    // 使用连续分贝采样数据（而非仅事件峰值）
    const samples = data.db_samples || [];
    let labels, values, thresholdData;
    if (samples.length > 0) {
      labels = samples.map((s) => {
        const d = new Date(s.ts);
        return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
      });
      values = samples.map((s) => s.db);
      thresholdData = samples.map((s) => s.threshold || null);
    } else {
      // 无采样数据时，用事件峰值兜底
      labels = data.events.map((e) => {
        const d = new Date(e.ts);
        return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit", hour12: false });
      });
      values = data.events.map((e) => e.peak_db);
      thresholdData = [];
    }

    const datasets = [{
      label: "分贝",
      data: values,
      borderColor: "#4ade80",
      backgroundColor: "rgba(74,222,128,0.1)",
      tension: 0.3, pointRadius: 0, fill: true,
    }];
    if (thresholdData.length > 0) {
      datasets.push({
        label: "触发线",
        data: thresholdData,
        borderColor: "#f87171",
        borderDash: [5, 3], pointRadius: 0, fill: false,
      });
    }
    this.charts.db = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        ...this._commonOpts(),
        scales: {
          ...this._commonOpts().scales,
          y: { ...this._commonOpts().scales.y, suggestedMin: 20, suggestedMax: 80 },
        },
      },
    });
  },

  _renderDaily(data) {
    this._destroy("daily");
    const labels = data.daily.map((d) => d.day.slice(5));
    const counts = data.daily.map((d) => d.count);
    const ctx = document.getElementById("chart-daily");
    this.charts.daily = new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ label: "事件数", data: counts, backgroundColor: "#22d3ee" }] },
      options: this._commonOpts(),
    });
  },

  _renderHourly(data) {
    this._destroy("hourly");
    const labels = Array.from({ length: 24 }, (_, i) => i + "时");
    const ctx = document.getElementById("chart-hourly");
    this.charts.hourly = new Chart(ctx, {
      type: "bar",
      data: { labels, datasets: [{ label: "事件数", data: data.hourly, backgroundColor: "#fbbf24" }] },
      options: this._commonOpts(),
    });
  },

  _renderLevel(data) {
    this._destroy("level");
    const ld = data.level_dist;
    const ctx = document.getElementById("chart-level");
    this.charts.level = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: ["轻提醒", "中警告", "强干预"],
        datasets: [{ data: [ld[1], ld[2], ld[3]], backgroundColor: ["#4ade80", "#fbbf24", "#f87171"] }],
      },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { labels: { color: "#9ca3af" } } } },
    });
  },

  _renderEventList(data) {
    const ul = document.getElementById("history-event-list");
    ul.innerHTML = "";
    const events = (data.events || []).slice().reverse(); // 最新在前
    if (events.length === 0) {
      const li = document.createElement("li");
      li.className = "hev-empty";
      li.textContent = "暂无记录";
      ul.appendChild(li);
      return;
    }
    const lvlNames = { 1: "轻提醒", 2: "中警告", 3: "强干预" };
    events.forEach((e) => {
      const li = document.createElement("li");
      const lvl = e.level_triggered || 0;
      li.className = "lvl-" + lvl;
      const d = new Date(e.ts);
      const time = d.toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
      const triggered = e.level_triggered !== null;
      const desc = triggered ? `${lvlNames[lvl] || "L" + lvl}` : "未触发";
      li.innerHTML = `<span>${desc} · 均${e.avg_db.toFixed(1)}dB · ${e.duration_ms}ms<span class="hev-time">${time}</span></span>` +
                     `<span class="hev-db">${e.peak_db.toFixed(1)}dB</span>`;
      ul.appendChild(li);
    });
  },
};
