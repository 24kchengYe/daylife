"""数据迁移：把多活动 entry 拆分成独立 entry

每个 entry 的 content 按 ，,、；;。 拆分，每条子项变成一条独立的 entry。
保留原始 entry 的 date、status、source 等字段。
利用 data_json 里已有的子项分类结果（如果有的话）。

运行前会备份数据库。
"""

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from daylife.core.database import get_db_path, get_session
from daylife.core.models import Category, DailyEntry

SEP = re.compile(r'[，,、；;。]+')


def main():
    db_path = get_db_path()

    # 备份数据库
    backup_path = db_path.parent / f"daylife_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(db_path, backup_path)
    print(f"数据库已备份: {backup_path}")

    session = get_session()

    # 加载分类映射
    cat_map = {}
    for c in session.query(Category).all():
        cat_map[c.name] = c.id

    # 获取所有 entry
    entries = session.query(DailyEntry).order_by(DailyEntry.date, DailyEntry.id).all()
    print(f"当前 entry 数: {len(entries)}")

    to_delete = []
    to_add = []

    for entry in entries:
        parts = [p.strip() for p in SEP.split(entry.content) if p.strip()]

        if len(parts) <= 1:
            # 不需要拆分，跳过
            continue

        # 解析 data_json 里的子项分类
        sub_cats = {}
        if entry.data_json:
            try:
                sub_cats = json.loads(entry.data_json)
            except Exception:
                pass

        # 创建新 entry
        for part in parts:
            cat_name = sub_cats.get(part)
            cat_id = cat_map.get(cat_name) if cat_name else entry.category_id

            new_entry = DailyEntry(
                date=entry.date,
                category_id=cat_id,
                content=part,
                status=entry.status,
                start_time=entry.start_time,
                end_time=entry.end_time,
                duration_minutes=None,  # 拆分后时长不适用
                priority=entry.priority,
                notes=None,
                data_json=None,
                source=entry.source,
                ai_classified=1 if cat_id else 0,
            )
            to_add.append(new_entry)

        to_delete.append(entry.id)

    print(f"需拆分: {len(to_delete)} 条 → 新增 {len(to_add)} 条")
    print(f"保留不拆分: {len(entries) - len(to_delete)} 条")
    print(f"拆分后总计: {len(entries) - len(to_delete) + len(to_add)} 条")

    confirm = input("\n确认执行? (y/N): ").strip().lower()
    if confirm != 'y':
        print("已取消")
        session.close()
        return

    # 删除旧 entry
    session.query(DailyEntry).filter(DailyEntry.id.in_(to_delete)).delete(synchronize_session=False)
    session.flush()

    # 添加新 entry
    for e in to_add:
        session.add(e)

    session.commit()

    final_count = session.query(DailyEntry).count()
    print(f"\n迁移完成! 当前 entry 数: {final_count}")
    print(f"数据库备份在: {backup_path}")

    # 统计未分类的
    uncl = session.query(DailyEntry).filter(DailyEntry.ai_classified == 0).count()
    print(f"未AI分类: {uncl} 条（需要重新点 AI 自动分类）")

    session.close()


if __name__ == "__main__":
    main()
