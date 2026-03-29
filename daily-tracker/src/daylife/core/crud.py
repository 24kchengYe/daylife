"""数据访问层 - 封装所有 CRUD 操作

提供对 daily_entries、categories、tags、attachments、import_metadata 表的
底层增删改查操作，供业务服务层调用。
"""

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from daylife.core.models import (
    Attachment,
    Category,
    DailyEntry,
    ImportMetadata,
    Tag,
    entry_tags,
)


# ══════════════════════════════════════════════════════════════
# DailyEntry CRUD
# ══════════════════════════════════════════════════════════════


def create_entry(session: Session, **kwargs) -> DailyEntry:
    """创建一条活动记录

    Args:
        session: 数据库会话
        **kwargs: DailyEntry 字段（date, content, status, category_id 等）
    Returns:
        新创建的 DailyEntry 实例
    """
    entry = DailyEntry(**kwargs)
    session.add(entry)
    session.flush()
    return entry


def get_entry_by_id(session: Session, entry_id: int) -> DailyEntry | None:
    """按 ID 获取单条记录（预加载分类和标签）"""
    return (
        session.query(DailyEntry)
        .options(
            joinedload(DailyEntry.category),
            joinedload(DailyEntry.tags),
            joinedload(DailyEntry.attachments),
        )
        .filter(DailyEntry.id == entry_id)
        .first()
    )


def get_entries_by_date(session: Session, target_date: date) -> list[DailyEntry]:
    """获取指定日期的所有记录，按开始时间排序"""
    return (
        session.query(DailyEntry)
        .options(joinedload(DailyEntry.category), joinedload(DailyEntry.tags))
        .filter(DailyEntry.date == target_date)
        .order_by(DailyEntry.start_time, DailyEntry.created_at)
        .all()
    )


def get_entries_by_date_range(
    session: Session,
    date_from: date,
    date_to: date,
    category_id: int | None = None,
    status: str | None = None,
) -> list[DailyEntry]:
    """按日期范围查询记录，支持按分类和状态过滤"""
    q = (
        session.query(DailyEntry)
        .options(joinedload(DailyEntry.category), joinedload(DailyEntry.tags))
        .filter(DailyEntry.date >= date_from, DailyEntry.date <= date_to)
    )
    if category_id is not None:
        q = q.filter(DailyEntry.category_id == category_id)
    if status is not None:
        q = q.filter(DailyEntry.status == status)
    return q.order_by(DailyEntry.date.desc(), DailyEntry.start_time).all()


def search_entries(
    session: Session,
    keyword: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    category_id: int | None = None,
    status: str | None = None,
    tag_names: list[str] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[DailyEntry]:
    """综合搜索记录，支持关键字、日期、分类、状态、标签多维过滤"""
    q = session.query(DailyEntry).options(
        joinedload(DailyEntry.category), joinedload(DailyEntry.tags)
    )

    if keyword:
        # 优先使用 FTS5 全文搜索索引，回退到 LIKE
        try:
            from sqlalchemy import text
            fts_ids = session.execute(
                text("SELECT rowid FROM entries_fts WHERE entries_fts MATCH :q"),
                {"q": keyword}
            ).scalars().all()
            if fts_ids:
                q = q.filter(DailyEntry.id.in_(fts_ids))
            else:
                q = q.filter(DailyEntry.content.contains(keyword))
        except Exception:
            q = q.filter(DailyEntry.content.contains(keyword))
    if date_from:
        q = q.filter(DailyEntry.date >= date_from)
    if date_to:
        q = q.filter(DailyEntry.date <= date_to)
    if category_id is not None:
        q = q.filter(DailyEntry.category_id == category_id)
    if status:
        q = q.filter(DailyEntry.status == status)
    if tag_names:
        # 筛选包含指定标签的记录
        q = q.join(DailyEntry.tags).filter(Tag.name.in_(tag_names))

    q = q.order_by(DailyEntry.date.desc(), DailyEntry.created_at.desc())
    offset = (page - 1) * page_size
    return q.offset(offset).limit(page_size).all()


def count_entries(
    session: Session,
    date_from: date | None = None,
    date_to: date | None = None,
    status: str | None = None,
) -> int:
    """统计符合条件的记录总数"""
    q = session.query(func.count(DailyEntry.id))
    if date_from:
        q = q.filter(DailyEntry.date >= date_from)
    if date_to:
        q = q.filter(DailyEntry.date <= date_to)
    if status:
        q = q.filter(DailyEntry.status == status)
    return q.scalar() or 0


def update_entry(session: Session, entry_id: int, **kwargs) -> DailyEntry | None:
    """更新记录的指定字段

    Args:
        session: 数据库会话
        entry_id: 记录 ID
        **kwargs: 要更新的字段及其值
    Returns:
        更新后的 DailyEntry，或 None（记录不存在时）
    """
    entry = session.query(DailyEntry).filter_by(id=entry_id).first()
    if not entry:
        return None
    for key, value in kwargs.items():
        if hasattr(entry, key):
            setattr(entry, key, value)
    session.flush()
    return entry


def delete_entry(session: Session, entry_id: int) -> bool:
    """删除一条记录，成功返回 True"""
    entry = session.query(DailyEntry).filter_by(id=entry_id).first()
    if not entry:
        return False
    session.delete(entry)
    session.flush()
    return True


# ══════════════════════════════════════════════════════════════
# Category CRUD
# ══════════════════════════════════════════════════════════════


def list_categories(session: Session) -> list[Category]:
    """获取所有分类，按排序权重排列"""
    return session.query(Category).order_by(Category.sort_order).all()


def get_category_by_name(session: Session, name: str) -> Category | None:
    """按名称查找分类"""
    return session.query(Category).filter_by(name=name).first()


def get_category_by_id(session: Session, category_id: int) -> Category | None:
    """按 ID 查找分类"""
    return session.query(Category).filter_by(id=category_id).first()


def create_category(
    session: Session, name: str, icon: str | None = None,
    color: str | None = None, sort_order: int = 0,
) -> Category:
    """创建新分类"""
    cat = Category(name=name, icon=icon, color=color, sort_order=sort_order)
    session.add(cat)
    session.flush()
    return cat


def update_category(session: Session, category_id: int, **kwargs) -> Category | None:
    """更新分类信息"""
    cat = session.query(Category).filter_by(id=category_id).first()
    if not cat:
        return None
    for key, value in kwargs.items():
        if hasattr(cat, key):
            setattr(cat, key, value)
    session.flush()
    return cat


# ══════════════════════════════════════════════════════════════
# Tag CRUD
# ══════════════════════════════════════════════════════════════


def get_or_create_tag(session: Session, name: str, color: str | None = None) -> Tag:
    """获取或创建标签（标签名唯一）"""
    tag = session.query(Tag).filter_by(name=name).first()
    if not tag:
        tag = Tag(name=name, color=color)
        session.add(tag)
        session.flush()
    return tag


def list_tags(session: Session) -> list[Tag]:
    """获取所有标签"""
    return session.query(Tag).order_by(Tag.name).all()


def get_popular_tags(session: Session, limit: int = 20) -> list[dict]:
    """获取高频使用标签及其使用次数"""
    rows = (
        session.query(Tag.name, Tag.color, func.count(entry_tags.c.entry_id).label("count"))
        .join(entry_tags, Tag.id == entry_tags.c.tag_id)
        .group_by(Tag.id)
        .order_by(func.count(entry_tags.c.entry_id).desc())
        .limit(limit)
        .all()
    )
    return [{"name": r.name, "color": r.color, "count": r.count} for r in rows]


def add_tags_to_entry(session: Session, entry: DailyEntry, tag_names: list[str]) -> None:
    """为记录添加标签（自动创建不存在的标签）"""
    for name in tag_names:
        tag = get_or_create_tag(session, name)
        if tag not in entry.tags:
            entry.tags.append(tag)
    session.flush()


def set_entry_tags(session: Session, entry: DailyEntry, tag_names: list[str]) -> None:
    """替换记录的所有标签"""
    entry.tags.clear()
    add_tags_to_entry(session, entry, tag_names)


# ══════════════════════════════════════════════════════════════
# Attachment CRUD
# ══════════════════════════════════════════════════════════════


def create_attachment(
    session: Session, entry_id: int, file_path: str,
    file_type: str | None = None, file_size: int | None = None,
) -> Attachment:
    """为记录添加附件"""
    att = Attachment(
        entry_id=entry_id, file_path=file_path,
        file_type=file_type, file_size=file_size,
    )
    session.add(att)
    session.flush()
    return att


def get_attachments_by_entry(session: Session, entry_id: int) -> list[Attachment]:
    """获取记录的所有附件"""
    return session.query(Attachment).filter_by(entry_id=entry_id).all()


def delete_attachment(session: Session, attachment_id: int) -> bool:
    """删除附件记录"""
    att = session.query(Attachment).filter_by(id=attachment_id).first()
    if not att:
        return False
    session.delete(att)
    session.flush()
    return True


# ══════════════════════════════════════════════════════════════
# ImportMetadata CRUD
# ══════════════════════════════════════════════════════════════


def create_import_record(
    session: Session, source_file: str, import_type: str,
    rows_imported: int = 0, rows_skipped: int = 0,
    date_range_start: date | None = None, date_range_end: date | None = None,
    color_mapping: str | None = None, notes: str | None = None,
) -> ImportMetadata:
    """创建导入记录"""
    record = ImportMetadata(
        source_file=source_file, import_type=import_type,
        rows_imported=rows_imported, rows_skipped=rows_skipped,
        date_range_start=date_range_start, date_range_end=date_range_end,
        color_mapping=color_mapping, notes=notes,
    )
    session.add(record)
    session.flush()
    return record


def list_import_records(session: Session) -> list[ImportMetadata]:
    """获取所有导入历史，按时间倒序"""
    return session.query(ImportMetadata).order_by(ImportMetadata.imported_at.desc()).all()
