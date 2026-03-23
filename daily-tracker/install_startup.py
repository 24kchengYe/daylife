"""创建 Windows 开机自启快捷方式

运行一次即可：python install_startup.py
会在 Windows 启动文件夹创建 DayLife 快捷方式。
"""

import os
import sys


def create_startup_shortcut():
    try:
        import winshell
    except ImportError:
        # 用 PowerShell 创建快捷方式（不需要额外依赖）
        pass

    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup"
    )

    # 找到 daylife.exe 的路径
    scripts_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Python\Python313\Scripts"
    )
    daylife_exe = os.path.join(scripts_dir, "daylife.exe")

    if not os.path.exists(daylife_exe):
        # 尝试其他路径
        for p in sys.path:
            candidate = os.path.join(os.path.dirname(p), "Scripts", "daylife.exe")
            if os.path.exists(candidate):
                daylife_exe = candidate
                break

    shortcut_path = os.path.join(startup_dir, "DayLife.vbs")

    # 用 VBScript 隐藏窗口启动
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.Run """{daylife_exe}"" tray", 0, False
'''

    with open(shortcut_path, "w") as f:
        f.write(vbs_content)

    print(f"开机自启已配置！")
    print(f"  快捷方式: {shortcut_path}")
    print(f"  程序路径: {daylife_exe}")
    print(f"  命令: daylife tray")
    print(f"\n下次开机将自动以托盘模式启动 DayLife。")


def remove_startup_shortcut():
    startup_dir = os.path.join(
        os.environ.get("APPDATA", ""),
        r"Microsoft\Windows\Start Menu\Programs\Startup"
    )
    shortcut_path = os.path.join(startup_dir, "DayLife.vbs")
    if os.path.exists(shortcut_path):
        os.remove(shortcut_path)
        print("已移除开机自启。")
    else:
        print("未找到开机自启配置。")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true", help="移除开机自启")
    args = parser.parse_args()

    if args.remove:
        remove_startup_shortcut()
    else:
        create_startup_shortcut()
