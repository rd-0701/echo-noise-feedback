// WebSocket 客户端：实时分贝/事件/告警，自动重连（指数退避）
const WS = {
  sock: null,
  reconnectTimer: null,
  reconnectDelay: 1000,
  maxReconnectDelay: 30000,
  handlers: {},
  on(type, cb) {
    (this.handlers[type] = this.handlers[type] || []).push(cb);
  },
  _emit(msg) {
    const hs = this.handlers[msg.type] || [];
    hs.forEach((h) => { try { h(msg); } catch (e) { console.error(e); } });
    // 通配
    (this.handlers["*"] || []).forEach((h) => { try { h(msg); } catch (e) {} });
  },
  connect() {
    if (!API.hasToken()) return;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${proto}//${location.host}/ws?token=${encodeURIComponent(API.token)}`;
    try { this.sock = new WebSocket(url); } catch (e) { this._scheduleReconnect(); return; }
    this.sock.onopen = () => {
      console.log("WS 已连接");
      this.reconnectDelay = 1000; // 重置退避
      if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
    };
    this.sock.onmessage = (ev) => {
      try { this._emit(JSON.parse(ev.data)); } catch (e) {}
    };
    this.sock.onclose = () => { this.sock = null; this._scheduleReconnect(); };
    this.sock.onerror = () => { try { this.sock.close(); } catch (e) {} };
    // 心跳
    if (!this._ping) {
      this._ping = setInterval(() => {
        if (this.sock && this.sock.readyState === 1) {
          this.sock.send(JSON.stringify({ cmd: "ping" }));
        }
      }, 30000);
    }
  },
  _scheduleReconnect() {
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);
    // 指数退避：每次失败延迟翻倍，上限 30s
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
  },
  disconnect() {
    if (this.reconnectTimer) { clearTimeout(this.reconnectTimer); this.reconnectTimer = null; }
    if (this.sock) { try { this.sock.close(); } catch (e) {} this.sock = null; }
    this.reconnectDelay = 1000;
  },
};
