"""生成包含 URL+Token 的 QR 码。"""
import os
import qrcode

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TOKEN_FILE = os.path.join(DATA_DIR, "auth_token.txt")
QR_FILE = os.path.join(DATA_DIR, "login_qr.png")

def main():
    # 读取 Token
    token = None
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            token = f.read().strip()
    except FileNotFoundError:
        print("Token 文件不存在")
        return

    # 本地访问 URL
    local_url = f"http://192.168.5.6:8000/?token={token}"

    # 生成 QR 码
    qr = qrcode.QRCode(version=1, box_size=10, border=2,
                        error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(local_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(QR_FILE)

    print(f"QR 码已生成: {QR_FILE}")
    print(f"扫码后直接登录，无需手动输入密码")

    # 终端 ASCII 显示
    qr_terminal = qrcode.QRCode(version=1, box_size=1, border=1,
                                error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr_terminal.add_data(local_url)
    qr_terminal.make(fit=True)
    matrix = qr_terminal.get_matrix()
    print("\n扫描下方二维码用手机打开：\n")
    for row in matrix:
        line = "".join("  " if cell else "██" for cell in row)
        print("  " + line)
    print()

if __name__ == "__main__":
    main()