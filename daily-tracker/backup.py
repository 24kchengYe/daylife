"""自动备份数据库到 GitHub 仓库

用法：
    python backup.py          # 手动备份
    配合 Windows 任务计划程序每周自动执行
"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# 路径
DB_PATH = Path.home() / ".local" / "share" / "daylife" / "daylife.db"
REPO_DIR = Path(__file__).parent.parent  # 061daylife/
BACKUP_DIR = REPO_DIR / "backups"


def backup():
    if not DB_PATH.exists():
        print(f"[Backup] Database not found: {DB_PATH}")
        return

    BACKUP_DIR.mkdir(exist_ok=True)

    # 复制数据库
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"daylife_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_file)
    print(f"[Backup] Copied to {backup_file}")

    # 只保留最近 8 个备份
    backups = sorted(BACKUP_DIR.glob("daylife_*.db"), reverse=True)
    for old in backups[8:]:
        old.unlink()
        print(f"[Backup] Removed old: {old.name}")

    # Git commit + push
    subprocess.run(["git", "add", "backups/"], cwd=str(REPO_DIR))
    result = subprocess.run(
        ["git", "commit", "-m", f"backup: {timestamp}"],
        cwd=str(REPO_DIR),
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        subprocess.run(["git", "push"], cwd=str(REPO_DIR))
        print(f"[Backup] Pushed to GitHub")
    else:
        print(f"[Backup] No changes to commit")


if __name__ == "__main__":
    backup()
