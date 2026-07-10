"""从 Cloudflare Tunnel 输出提取 URL 并生成 QR 码。"""
import os
import re
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

def generate_qr(url_with_token):
    """生成 QR 码 PNG。"""
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

def main():
    # 读取 Token
    token = read_token()
    if not token:
        print("  无法读取 Token")
        return

    # 尝试从 URL_FILE 读取（如果之前启动过）
    tunnel_url = None
    if os.path.exists(URL_FILE):
        try:
            with open(URL_FILE, "r", encoding="utf-8") as f:
                content = f.read().strip()
                match = Tunnel_URL_RE.search(content)
                if match:
                    tunnel_url = match.group(0)
        except Exception:
            pass

    # 如果没有找到，尝试从 tunnel log 文件读取
    if not tunnel_url:
        log_file = os.path.join(BASE_DIR, "tunnel", "tunnel.log")
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    matches = Tunnel_URL_RE.findall(content)
                    if matches:
                        tunnel_url = matches[-1]  # 取最后一个
            except Exception:
                pass

    if not tunnel_url:
        print("  未找到 Tunnel URL，请稍后再试")
        return

    # 构建完整 URL
    full_url = f"{tunnel_url}/?token={token}"

    # 保存 URL
    with open(URL_FILE, "w", encoding="utf-8") as f:
        f.write(tunnel_url)

    # 生成 QR 码
    if generate_qr(full_url):
        print(f"  公网地址: {tunnel_url}")
        print(f"  QR码已生成: {QR_FILE}")

if __name__ == "__main__":
    main()