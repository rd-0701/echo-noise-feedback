"""Echo 一键启动：服务器 + Cloudflare Tunnel + QR 码。

用法：python scripts/start.py
功能：
  1. 启动 Echo 服务器
  2. 启动 Cloudflare Tunnel 获取公网 URL
  3. 生成包含 URL+Token 的 QR 码（手机扫码直接打开）
  4. 在终端显示 URL 和 QR 码
"""
import os
import sys
import re
import time
import subprocess
import threading
import signal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CF = os.path.join(BASE_DIR, "tunnel", "cloudflared.exe")
DATA_DIR = os.path.join(BASE_DIR, "data")
TOKEN_FILE = os.path.join(DATA_DIR, "auth_token.txt")
URL_FILE = os.path.join(DATA_DIR, "tunnel_url.txt")
QR_FILE = os.path.join(DATA_DIR, "tunnel_qr.png")

Tunnel_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def read_token():
    """读取访问 Token。"""
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def wait_for_port(port=8000, timeout=30):
    """等待端口就绪。"""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.5)
    return False


def generate_qr(url_with_token):
    """生成 QR 码 PNG 和终端 ASCII 显示。"""
    try:
        import qrcode
        # 生成 PNG
        qr = qrcode.QRCode(version=1, box_size=10, border=2,
                            error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(url_with_token)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(QR_FILE)
        print(f"\n  QR 码已保存到: {QR_FILE}")

        # 终端 ASCII 显示
        qr_terminal = qrcode.QRCode(version=1, box_size=1, border=1,
                                    error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr_terminal.add_data(url_with_token)
        qr_terminal.make(fit=True)
        # 用 Unicode 方块字符渲染
        matrix = qr_terminal.get_matrix()
        print("\n  扫描下方二维码用手机打开：\n")
        for row in matrix:
            line = "".join("  " if cell else "██" for cell in row)
            print("  " + line)
        print()
    except ImportError:
        print("  (qrcode 库未安装，无法生成 QR 码)")
        print(f"  请手动打开: {url_with_token}")


def main():
    # 检查 cloudflared
    if not os.path.exists(CF):
        print(f"错误: cloudflared.exe 不存在 ({CF})")
        print("请从 https://github.com/cloudflare/cloudflared/releases/latest 下载")
        print("文件: cloudflared-windows-amd64.exe，重命名为 cloudflared.exe")
        sys.exit(1)

    # 读取 Token
    token = read_token()
    if not token:
        # 先启动服务器让它生成 Token
        pass

    print("=" * 60)
    print("  Echo 噪音提醒 - 一键启动")
    print("=" * 60)

    # 检查端口是否已被占用
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 8000))
        s.close()
        print("\n  端口 8000 已被占用，请先关闭之前的 Echo 实例。")
        sys.exit(1)
    except (ConnectionRefusedError, socket.timeout, OSError):
        pass

    # 1. 启动服务器
    print("\n  [1/3] 启动 Echo 服务器...")
    server_proc = subprocess.Popen(
        [PY, "-m", "backend.main"],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    # 等待服务器就绪
    print("  等待服务器就绪...", end="", flush=True)
    if not wait_for_port(8000, timeout=30):
        print(" 失败!")
        print("  服务器启动超时，请检查日志。")
        server_proc.kill()
        sys.exit(1)
    print(" OK")

    # 读取 Token（服务器启动后生成）
    token = read_token()
    if not token:
        print("  警告: 无法读取 Token，QR 码将不含自动登录功能。")

    # 2. 启动 Tunnel
    print("\n  [2/3] 启动 Cloudflare Tunnel...")
    tunnel_proc = subprocess.Popen(
        [CF, "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    # 3. 等待获取 Tunnel URL
    print("  等待获取公网地址...", end="", flush=True)
    tunnel_url = None
    start_time = time.time()
    while time.time() - start_time < 60:
        line = tunnel_proc.stdout.readline()
        if not line:
            if tunnel_proc.poll() is not None:
                break
            continue
        line = line.strip()
        match = Tunnel_URL_RE.search(line)
        if match:
            tunnel_url = match.group(0)
            break
        print(".", end="", flush=True)

    if not tunnel_url:
        print(" 失败!")
        print("\n  无法获取 Tunnel URL。请检查网络连接。")
        print("  Cloudflared 输出:")
        # 读取剩余输出
        remaining = tunnel_proc.stdout.read()
        for line in remaining.splitlines()[-20:]:
            print(f"    {line}")
        server_proc.kill()
        tunnel_proc.kill()
        sys.exit(1)

    print(" OK")

    # 构建带 Token 的完整 URL
    if token:
        full_url = f"{tunnel_url}/?token={token}"
    else:
        full_url = tunnel_url

    # 保存 URL
    with open(URL_FILE, "w", encoding="utf-8") as f:
        f.write(tunnel_url)

    # 4. 生成 QR 码
    print("\n  [3/3] 生成二维码...")
    generate_qr(full_url)

    # 显示最终信息
    print("=" * 60)
    print(f"  公网地址: {tunnel_url}")
    print(f"  访问密码: {token or '(见 data/auth_token.txt)'}")
    print(f"  手机扫码: 打开 data/tunnel_qr.png 或用手机扫上方二维码")
    print("=" * 60)
    print("\n  按 Ctrl+C 停止服务和隧道。\n")

    # 保持运行，转发 tunnel 输出
    try:
        for line in tunnel_proc.stdout:
            print(f"  [tunnel] {line.rstrip()}")
    except KeyboardInterrupt:
        pass

    # 清理
    print("\n  正在停止...")
    try:
        tunnel_proc.terminate()
    except Exception:
        pass
    try:
        server_proc.terminate()
    except Exception:
        pass
    try:
        tunnel_proc.wait(timeout=5)
    except Exception:
        tunnel_proc.kill()
    try:
        server_proc.wait(timeout=5)
    except Exception:
        server_proc.kill()
    print("  已停止。")


if __name__ == "__main__":
    main()
