"""自动备份数据库到私有 GitHub 仓库 (daylife-backup)"""

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "daylife" / "daylife.db"
BACKUP_REPO = Path("D:/pythonPycharms/工具开发/061daylife-backup")


def backup():
    if not DB_PATH.exists():
        print(f"[Backup] Database not found: {DB_PATH}")
        return

    BACKUP_REPO.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_REPO / f"daylife_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_file)
    print(f"[Backup] Copied to {backup_file}")

    # 只保留最近 8 个备份
    backups = sorted(BACKUP_REPO.glob("daylife_*.db"), reverse=True)
    for old in backups[8:]:
        old.unlink()
        print(f"[Backup] Removed old: {old.name}")

    subprocess.run(["git", "add", "-A"], cwd=str(BACKUP_REPO))
    result = subprocess.run(
        ["git", "commit", "-m", f"backup: {timestamp}"],
        cwd=str(BACKUP_REPO), capture_output=True, text=True,
    )
    if result.returncode == 0:
        subprocess.run(["git", "push"], cwd=str(BACKUP_REPO))
        print(f"[Backup] Pushed to daylife-backup repo")
    else:
        print(f"[Backup] No changes to commit")


if __name__ == "__main__":
    backup()
