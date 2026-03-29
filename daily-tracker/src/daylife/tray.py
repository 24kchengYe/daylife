"""DayLife 系统托盘 — 后台常驻，托盘图标，点击打开浏览器

用法：
    daylife tray        # 启动托盘模式（后台服务 + 系统托盘图标）
    daylife tray --startup  # 同上，适合开机自启

托盘菜单：
    - 打开 DayLife      → 浏览器打开 Dashboard
    - 服务状态          → 显示端口和运行时长
    - 重启服务          → 重启 FastAPI
    - 退出              → 关闭一切
"""

import threading
import time
import webbrowser
from io import BytesIO

import pystray
from PIL import Image, ImageDraw, ImageFont


def create_icon_image():
    """生成一个简单的 DL 图标（紫色圆底白字）"""
    size = 64
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # 紫色圆
    draw.ellipse([2, 2, size - 2, size - 2], fill='#5c6bc0')
    # 白色文字 DL
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    draw.text((size // 2, size // 2), "DL", fill='white', font=font, anchor='mm')
    return img


class DayLifeTray:
    def __init__(self, host='127.0.0.1', port=8263):
        self.host = host
        self.port = port
        self.url = f'http://{host}:{port}'
        self.server_thread = None
        self.start_time = time.time()

    def start_server(self):
        """在后台线程启动 FastAPI"""
        import uvicorn
        from daylife.core.database import init_db
        init_db()
        uvicorn.run(
            "daylife.api.main:app",
            host=self.host,
            port=self.port,
            log_level="warning",
        )

    def open_browser(self, icon=None, item=None):
        webbrowser.open(self.url)

    def show_status(self, icon, item):
        uptime = int(time.time() - self.start_time)
        h, m = uptime // 3600, (uptime % 3600) // 60
        icon.notify(
            f"DayLife 运行中\n地址: {self.url}\n运行时长: {h}h {m}m",
            "DayLife Status"
        )

    def restart_server(self, icon, item):
        icon.notify("正在重启...", "DayLife")
        # 简单方案：告诉用户手动重启（uvicorn 不好优雅重启）
        icon.notify("请关闭后重新运行 daylife tray", "DayLife")

    def quit(self, icon, item):
        icon.stop()
        import os
        os._exit(0)

    def run(self):
        # 启动服务
        self.server_thread = threading.Thread(target=self.start_server, daemon=True)
        self.server_thread.start()

        # 等服务启动
        time.sleep(1.5)

        # 自动打开浏览器
        webbrowser.open(self.url)

        # 创建托盘
        icon = pystray.Icon(
            "daylife",
            create_icon_image(),
            "DayLife",
            menu=pystray.Menu(
                pystray.MenuItem("打开 DayLife", self.open_browser, default=True),
                pystray.MenuItem("服务状态", self.show_status),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", self.quit),
            )
        )
        icon.run()


def main(host='127.0.0.1', port=8263):
    tray = DayLifeTray(host, port)
    tray.run()


if __name__ == '__main__':
    main()
