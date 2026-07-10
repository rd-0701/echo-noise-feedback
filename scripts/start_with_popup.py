"""Echo一键启动：服务+Tunnel+自动弹出QR码窗口。

用法：python scripts/start_with_popup.py
"""
import os
import sys
import re
import time
import subprocess
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
CF = os.path.join(BASE_DIR, "tunnel", "cloudflared.exe")
DATA_DIR = os.path.join(BASE_DIR, "data")
TOKEN_FILE = os.path.join(DATA_DIR, "auth_token.txt")
URL_FILE = os.path.join(DATA_DIR, "tunnel_url.txt")
QR_FILE = os.path.join(DATA_DIR, "tunnel_qr.png")

Tunnel_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def read_token():
    """读取访问Token。"""
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
    """生成QR码PNG。"""
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=10, border=2,
                            error_correction=qrcode.constants.ERROR_CORRECT_L)
        qr.add_data(url_with_token)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(QR_FILE)
        return True
    except Exception as e:
        print(f"  生成QR码失败: {e}")
        return False


def open_qr_image():
    """用系统默认图片查看器打开QR码。"""
    if os.path.exists(QR_FILE):
        if os.name == "nt":
            os.startfile(QR_FILE)
        else:
            subprocess.Popen(["xdg-open", QR_FILE])
        return True
    return False


def main():
    print("=" * 60)
    print("  Echo 噪音提醒 - 一键启动（公网访问）")
    print("=" * 60)

    # 检查cloudflared
    if not os.path.exists(CF):
        print(f"\n  错误: cloudflared.exe 不存在 ({CF})")
        print("  请从 https://github.com/cloudflare/cloudflared/releases/latest 下载")
        sys.exit(1)

    # 检查端口
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect(("127.0.0.1", 8000))
        s.close()
        print("\n  端口8000已被占用，正在关闭旧进程...")
        result = subprocess.run(
            ["powershell", "-Command",
             "Get-NetTCPConnection -LocalPort 8000 -State Listen | "
             "ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }"],
            capture_output=True
        )
        time.sleep(2)
    except (ConnectionRefusedError, socket.timeout, OSError):
        pass

    # 1. 启动服务器
    print("\n  [1/3] 启动Echo服务器...")
    server_proc = subprocess.Popen(
        [PY, "-m", "backend.main"],
        cwd=BASE_DIR,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    print("  等待服务器就绪...", end="", flush=True)
    if not wait_for_port(8000, timeout=30):
        print(" 失败!")
        print("  服务器启动超时")
        server_proc.kill()
        sys.exit(1)
    print(" OK")

    # 读取Token
    token = read_token()
    if not token:
        print("  警告: 无法读取Token")

    # 2. 启动Tunnel
    print("\n  [2/3] 启动Cloudflare Tunnel...")
    tunnel_proc = subprocess.Popen(
        [CF, "tunnel", "--url", "http://localhost:8000", "--no-autoupdate"],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )

    # 3. 等待获取Tunnel URL
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
        print("\n  无法获取Tunnel URL，请检查网络连接")
        server_proc.kill()
        tunnel_proc.kill()
        sys.exit(1)

    print(" OK")

    # 构建完整URL
    full_url = f"{tunnel_url}/?token={token}" if token else tunnel_url

    # 保存URL
    with open(URL_FILE, "w", encoding="utf-8") as f:
        f.write(tunnel_url)

    # 4. 生成QR码
    print("\n  [3/3] 生成二维码...")
    if generate_qr(full_url):
        print(f"  QR码已生成: {QR_FILE}")

    # 5. 打开QR码窗口
    print("\n  正在打开QR码窗口...")
    if open_qr_image():
        print("  [OK] QR码窗口已弹出，请用手机扫码")
    else:
        print("  [FAIL] QR码文件不存在")

    # 显示最终信息
    print("\n" + "=" * 60)
    print(f"  公网地址: {tunnel_url}")
    print(f"  访问密码: {token}")
    print("=" * 60)
    print("\n  服务已启动，窗口关闭后请勿关闭此命令窗口")
    print("  按 Ctrl+C 可停止服务\n")

    # 保持运行
    try:
        while True:
            time.sleep(1)
            # 检查进程是否还在运行
            if server_proc.poll() is not None:
                print("\n  服务器已停止")
                break
            if tunnel_proc.poll() is not None:
                print("\n  Tunnel已停止")
                break
    except KeyboardInterrupt:
        print("\n\n  正在停止...")

    # 清理
    for proc in (tunnel_proc, server_proc):
        try:
            proc.terminate()
        except Exception:
            pass
    print("  已停止。")


if __name__ == "__main__":
    main()