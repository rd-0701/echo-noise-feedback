# Echo 噪音反馈系统

实时噪音检测与分级反馈系统。通过麦克风采集环境噪音，自动识别超标噪音并以分级声音信号进行反馈提醒，支持手机远程控制。

## 功能特性

- **实时噪音检测** — 基于 RMS/dBFS/dB SPL 分析，频谱重心区分稳态噪音与突发撞击
- **三级分级反馈** — 根据噪音超标程度自动选择 L1(轻提醒)/L2(中警告)/L3(强干预)反馈音
- **动态基线学习** — 开机自动学习环境底噪，浮动阈值适应不同环境
- **自激抑制** — 播放反馈音时自动屏蔽检测，引用计数支持并发播放
- **手机远程控制** — Web UI + WebSocket 实时推送，支持公网访问（Cloudflare Tunnel）
- **声音工坊** — 内置 7 种反馈音合成，支持上传/录制/合成/EQ 调整
- **历史分析** — 分贝趋势图、每日事件数、时段分布、等级分布可视化
- **定时调度** — 设定时间窗内按间隔自动播放提醒
- **PWA 支持** — 可添加到手机主屏幕，离线缓存核心资源

## 系统架构

```
echo-project/
├── backend/
│   ├── api/            # REST API + WebSocket 路由
│   │   ├── routes.py   # 状态/配置/触发/历史/设备 API
│   │   ├── websocket.py# WebSocket 实时推送
│   │   └── workshop.py # 声音工坊 API（上传/录制/合成/EQ）
│   ├── audio/          # 音频采集与分析
│   │   ├── analyzer.py # RMS/dBFS/dB SPL/频谱重心计算
│   │   ├── capture.py  # sounddevice 输入流
│   │   ├── player.py   # 反馈音播放（引用计数抑制）
│   │   ├── sounds.py   # 内置音合成（嗡声/脉冲/扫频/蜂鸣/警报）
│   │   └── bluetooth.py # 音频输出设备监控
│   ├── core/           # 核心引擎
│   │   ├── detector.py     # 噪音检测状态机
│   │   ├── baseline.py     # 环境基线学习
│   │   ├── strategy.py     # 三级分级策略
│   │   ├── suppression.py  # 自激循环抑制
│   │   ├── scheduler.py     # 定时调度（APScheduler）
│   │   └── events.py       # 事件总线
│   ├── db/             # SQLite 数据层
│   ├── auth.py         # Token 认证中间件
│   ├── config.py       # 配置管理（JSON 持久化）
│   └── main.py         # FastAPI 应用入口
├── frontend/           # 移动优先 PWA 前端
│   ├── index.html      # 单页应用
│   ├── css/style.css   # 深色主题
│   ├── js/             # 模块化 JS（无框架依赖）
│   │   ├── api.js      # REST 客户端 + Token 管理
│   │   ├── ws.js       # WebSocket 客户端（指数退避重连）
│   │   ├── dashboard.js# 仪表盘（实时分贝/事件/手动触发）
│   │   ├── settings.js # 设置页（配置加载/保存/验证）
│   │   ├── history.js  # 历史分析（Chart.js 图表）
│   │   └── workshop.js # 声音管理
│   ├── manifest.json  # PWA Manifest
│   └── sw.js          # Service Worker
├── scripts/            # 启动脚本
│   ├── start_with_popup.py # 一键启动（服务+Tunnel+QR码弹窗）
│   └── create_shortcut.vbs # 桌面快捷方式
├── tunnel/             # Cloudflare Tunnel + 测试脚本
├── requirements.txt    # Python 依赖
└── .gitignore
```

## 快速开始

### 环境要求

- **Python 3.11+**
- **Windows 10/11**（音频 API 依赖 pycaw，Linux/Mac 需适配）
- 麦克风（内置或外接）
- 音频输出设备（蓝牙音响或扬声器）

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/your-username/echo-project.git
cd echo-project

# 2. 创建虚拟环境
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

# 3. 安装依赖
pip install -r requirements.txt
```

### 启动

#### 方式一：本地访问（局域网）

```bash
python -m backend.main
```

浏览器打开 `http://localhost:8000`，终端会显示访问 Token。

#### 方式二：公网访问（跨网络）

下载 [cloudflared](https://github.com/cloudflare/cloudflared/releases/latest)，重命名为 `cloudflared.exe` 放入 `tunnel/` 目录，然后：

```bash
python scripts/start_with_popup.py
```

脚本会自动：
1. 启动 Echo 服务器
2. 启动 Cloudflare Tunnel 获取公网 URL
3. 生成包含 URL+Token 的 QR 码
4. 弹出 QR 码图片窗口

手机扫码即可连接，支持移动数据网络访问。

### Token 认证

首次启动时系统自动生成 Token（`data/auth_token.txt`）。所有 `/api/*` 端点和 WebSocket 连接需要 Token 认证。前端支持：
- URL 参数自动登录：`https://your-url/?token=xxx`
- 手动输入密码登录
- Token 持久化到 localStorage

## API 文档

### 认证

所有 `/api/*` 端点需要 `Authorization: Bearer <token>` 头或 `?token=<token>` 查询参数。

### 核心端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（无需认证） |
| GET | `/api/status` | 当前状态（分贝/基线/阈值/检测状态） |
| GET | `/api/diagnostics` | 诊断信息（麦克风信号/校准参数） |
| GET | `/api/config` | 获取完整配置 |
| PUT | `/api/config` | 更新配置（深合并） |
| POST | `/api/toggle` | 开关检测 `{enabled: bool}` |
| POST | `/api/auto-feedback` | 开关自动反馈 `{auto_feedback: bool}` |
| POST | `/api/trigger` | 手动触发 `{level: 1\|2\|3, volume?, sound_id?}` |
| POST | `/api/preview` | 试听音频 `{sound_id, volume}` |
| POST | `/api/baseline/reset` | 重置基线学习 |
| GET | `/api/history?range_=day\|week\|month` | 历史数据（事件/播放/采样/图表聚合） |
| GET | `/api/sounds` | 音频库列表 |
| DELETE | `/api/sounds/{id}` | 删除音频（内置不可删） |
| POST | `/api/sounds/bind` | 绑定音频到等级 `{level, sound_id}` |
| POST | `/api/sounds/upload` | 上传音频（wav/mp3/flac/ogg，限 10MB） |
| POST | `/api/sounds/record` | 录制音频 `{seconds: 1-60}` |
| POST | `/api/sounds/synthesize` | 合成音频 `{name, kind, f0, f1, duration_s}` |
| POST | `/api/sounds/{id}/equalize` | 频谱调整 `{bands: [{freq_low, freq_high, gain_db}]}` |
| GET | `/api/devices` | 音频设备列表 |
| POST | `/api/devices/set-input` | 切换输入设备 |
| POST | `/api/devices/test` | 测试输入设备信号 |

### WebSocket

```
ws://host/ws?token=<token>     # 本地
wss://host/ws?token=<token>    # 公网（TLS）
```

推送消息类型：

| type | 内容 |
|------|------|
| `db` | 实时分贝值（10Hz 节流） |
| `event` | 噪音事件（峰值/均值/时长/等级/频谱重心） |
| `playback` | 播放记录 |
| `trigger` | 触发反馈 |
| `bt_status` | 蓝牙连接状态变化 |
| `alert` | 系统告警 |
| `info` | 系统信息 |

客户端可发送 `{"cmd":"ping"}` 心跳，服务端回复 `{"type":"pong"}`。

## 配置说明

配置存储在 `data/config.json`，首次启动自动生成。关键参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `audio.calibration_offset` | 90.0 | dBFS→dB SPL 校准偏移 |
| `detection.baseline_learn_seconds` | 60 | 基线学习时长（秒） |
| `detection.threshold_offset_db` | 15.0 | 基线+偏移=触发阈值 |
| `detection.absolute_threshold_db` | 40.0 | 最低触发分贝 |
| `detection.confirm_blocks` | 5 | 连续超阈值块数确认 |
| `detection.min_duration_ms` | 300 | 最短触发时长 |
| `strategy.l1_delta_db` | 8.0 | 超阈值 0-8dB → L1 |
| `strategy.l2_delta_db` | 18.0 | 超阈值 8-18dB → L2，>18 → L3 |
| `suppression.cooldown_s` | 3.0 | 播放后冷却时间 |

## 检测引擎原理

1. **音频采集** — sounddevice InputStream 回调 → 队列 → 工作线程处理
2. **分析** — 每个 block 计算 RMS → dBFS → dB SPL + 频谱重心
3. **基线学习** — 前 60 秒采样中位数作为底噪基线，每 10 分钟缓慢适应（90%旧+10%新）
4. **状态机** — `IDLE → SUSPECT → COOLDOWN`：连续 N 块超阈值且持续够久 → 确认事件
5. **瞬态过滤** — 高频重心(>4kHz) + 短时长 → 判定为撞击声，忽略
6. **分级触发** — 根据峰值分贝与阈值的差值决定 L1/L2/L3，动态音量映射
7. **自激抑制** — 播放期+冷却期屏蔽检测，引用计数支持并发播放

## 技术栈

- **后端**: Python 3.11+, FastAPI, uvicorn, sounddevice, numpy, scipy, APScheduler, pycaw
- **前端**: 原生 HTML/CSS/JS（无框架），Chart.js, PWA Service Worker
- **数据库**: SQLite（线程安全连接 + 全局锁）
- **实时通信**: WebSocket（事件总线桥接 asyncio 事件循环）
- **公网穿透**: Cloudflare Tunnel（免费，无需域名）

## 开发

```bash
# 开发模式（热重载）
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 运行测试
python tunnel/smoke_test.ps1    # 冒烟测试
python tunnel/auth_test.ps1     # 认证测试
python tunnel/e2e_test.ps1      # 端到端测试
python tunnel/ws_test.py        # WebSocket 测试
```

## 许可证

[MIT License](LICENSE)
