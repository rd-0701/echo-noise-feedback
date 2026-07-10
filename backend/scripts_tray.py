"""系统托盘启动器：pystray 图标 + 后台运行 uvicorn。"""
import threading
import webbrowser
from PIL import Image, ImageDraw

# 提供模块路径 backend.scripts_tray 供 run.bat 调用


def _create_icon(color):
    img = Image.new("RGBA", (64, 64), (15, 20, 25, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((12, 12, 52, 52), fill=color)
    return img


def main():
    import pystray
    from .main import run_in_thread

    state = {"running": True}

    def on_open(icon, item):
        webbrowser.open(f"http://127.0.0.1:8000/")

    def on_exit(icon, item):
        state["running"] = False
        icon.stop()

    # 后台启动 uvicorn
    run_in_thread()

    menu = pystray.Menu(
        pystray.MenuItem("打开控制台", on_open, default=True),
        pystray.MenuItem("退出", on_exit),
    )
    icon = pystray.Icon("Echo", _create_icon((74, 222, 128)), "Echo 噪音反馈", menu)
    icon.run()


if __name__ == "__main__":
    main()
