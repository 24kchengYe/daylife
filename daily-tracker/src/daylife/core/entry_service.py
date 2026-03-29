"""业务逻辑层 - 活动记录的增删改查

在 crud.py 基础上封装业务逻辑：分类解析、标签处理、时长自动计算等。
供 CLI、API、MCP 等上层调用。
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session

from daylife.core import crud
from daylife.core.models import DailyEntry
from daylife.core.schemas import EntryCreate, EntryQuery, EntryUpdate


class EntryService:
    """活动记录业务服务"""

    def __init__(self, session: Session):
        self.session = session

    # ── 创建记录 ──

    def add_entry(self, data: EntryCreate) -> DailyEntry:
        """添加一条活动记录

        自动处理：
        - 分类名 → category_id 解析
        - 标签自动创建
        - start_time + end_time → duration_minutes 自动计算
        """
        # 解析分类名
        category_id = None
        ai_classified = 0
        if data.category:
            cat = crud.get_category_by_name(self.session, data.category)
            if cat:
                category_id = cat.id
                ai_classified = 1  # 用户手动选了分类，标记为已分类

        # 自动计算时长
        duration = data.duration_minutes
        if duration is None and data.start_time and data.end_time:
            duration = self._calc_duration(data.start_time, data.end_time)

        # 创建记录
        entry = crud.create_entry(
            self.session,
            date=data.date,
            category_id=category_id,
            content=data.content,
            status=data.status,
            start_time=data.start_time,
            end_time=data.end_time,
            duration_minutes=duration,
            priority=data.priority,
            notes=data.notes,
            source=data.source,
            ai_classified=ai_classified,
        )

        # 处理标签
        if data.tags:
            crud.add_tags_to_entry(self.session, entry, data.tags)

        self.session.commit()
        self.session.refresh(entry)
        return entry

    # ── 查询记录 ──

    def get_entry(self, entry_id: int) -> DailyEntry | None:
        """按 ID 获取单条记录"""
        return crud.get_entry_by_id(self.session, entry_id)

    def get_today_entries(self) -> list[DailyEntry]:
        """获取今日所有记录"""
        return crud.get_entries_by_date(self.session, date.today())

    def get_entries_by_date(self, target_date: date) -> list[DailyEntry]:
        """获取指定日期的所有记录"""
        return crud.get_entries_by_date(self.session, target_date)

    def get_entries_by_date_range(
        self, date_from: date, date_to: date,
        category: str | None = None, status: str | None = None,
    ) -> list[DailyEntry]:
        """按日期范围查询，支持分类名和状态过滤"""
        category_id = None
        if category:
            cat = crud.get_category_by_name(self.session, category)
            if cat:
                category_id = cat.id
        return crud.get_entries_by_date_range(
            self.session, date_from, date_to, category_id, status
        )

    def search(self, query: EntryQuery) -> list[DailyEntry]:
        """综合搜索（支持关键字、日期、分类、状态、标签、分页）"""
        category_id = None
        if query.category:
            cat = crud.get_category_by_name(self.session, query.category)
            if cat:
                category_id = cat.id

        return crud.search_entries(
            self.session,
            keyword=query.keyword,
            date_from=query.date_from,
            date_to=query.date_to,
            category_id=category_id,
            status=query.status,
            tag_names=query.tags,
            page=query.page,
            page_size=query.page_size,
        )

    # ── 修改记录 ──

    def update_entry(self, entry_id: int, data: EntryUpdate) -> DailyEntry | None:
        """更新记录，支持部分更新

        自动处理分类名解析和标签替换。
        """
        entry = crud.get_entry_by_id(self.session, entry_id)
        if not entry:
            return None

        update_fields = data.model_dump(exclude_unset=True)

        # 处理分类名 → category_id
        if "category" in update_fields:
            cat_name = update_fields.pop("category")
            if cat_name:
                cat = crud.get_category_by_name(self.session, cat_name)
                if cat:
                    entry.category_id = cat.id

        # 处理标签替换
        if "tags" in update_fields:
            tag_names = update_fields.pop("tags")
            if tag_names is not None:
                crud.set_entry_tags(self.session, entry, tag_names)

        # 更新普通字段
        for key, value in update_fields.items():
            if hasattr(entry, key):
                setattr(entry, key, value)

        # 重新计算时长
        if entry.start_time and entry.end_time and entry.duration_minutes is None:
            entry.duration_minutes = self._calc_duration(entry.start_time, entry.end_time)

        self.session.commit()
        self.session.refresh(entry)
        return entry

    # ── 删除记录 ──

    def delete_entry(self, entry_id: int) -> bool:
        """删除一条记录"""
        result = crud.delete_entry(self.session, entry_id)
        if result:
            self.session.commit()
        return result

    # ── 批量操作 ──

    def batch_create(self, entries_data: list[EntryCreate]) -> list[DailyEntry]:
        """批量创建记录（用于数据导入等场景）"""
        # 预加载所有分类到缓存，避免循环查询
        _cat_cache = {c.name: c.id for c in crud.list_categories(self.session)}
        results = []
        for data in entries_data:
            category_id = None
            if data.category:
                category_id = _cat_cache.get(data.category)

            duration = data.duration_minutes
            if duration is None and data.start_time and data.end_time:
                duration = self._calc_duration(data.start_time, data.end_time)

            entry = crud.create_entry(
                self.session,
                date=data.date,
                category_id=category_id,
                content=data.content,
                status=data.status,
                start_time=data.start_time,
                end_time=data.end_time,
                duration_minutes=duration,
                priority=data.priority,
                notes=data.notes,
                source=data.source,
            )
            if data.tags:
                crud.add_tags_to_entry(self.session, entry, data.tags)
            results.append(entry)

        self.session.commit()
        return results

    def mark_completed(self, entry_id: int) -> DailyEntry | None:
        """将记录标记为已完成"""
        entry = crud.update_entry(self.session, entry_id, status="completed")
        if entry:
            self.session.commit()
        return entry

    def mark_incomplete(self, entry_id: int) -> DailyEntry | None:
        """将记录标记为未完成"""
        entry = crud.update_entry(self.session, entry_id, status="incomplete")
        if entry:
            self.session.commit()
        return entry

    # ── 分类管理 ──

    def list_categories(self):
        """列出所有分类"""
        return crud.list_categories(self.session)

    def get_category_stats(self, date_from: date, date_to: date) -> list[dict]:
        """获取日期范围内各分类的记录数统计"""
        categories = crud.list_categories(self.session)
        result = []
        for cat in categories:
            entries = crud.get_entries_by_date_range(
                self.session, date_from, date_to, category_id=cat.id
            )
            if not entries:
                continue
            completed = sum(1 for e in entries if e.status == "completed")
            total_minutes = sum(e.duration_minutes or 0 for e in entries)
            result.append({
                "category": cat.name,
                "icon": cat.icon,
                "color": cat.color,
                "count": len(entries),
                "total_minutes": total_minutes,
                "completion_rate": (completed / len(entries) * 100) if entries else 0,
            })
        return result

    # ── 工具方法 ──

    @staticmethod
    def _calc_duration(start: time, end: time) -> int:
        """计算两个时间点之间的分钟数"""
        start_dt = datetime.combine(date.today(), start)
        end_dt = datetime.combine(date.today(), end)
        # 处理跨午夜的情况
        if end_dt < start_dt:
            end_dt += timedelta(days=1)
        return int((end_dt - start_dt).total_seconds() / 60)
