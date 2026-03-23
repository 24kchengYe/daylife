"""数据库层测试 - 模型 + CRUD 操作

使用内存 SQLite 数据库进行测试，确保所有 CRUD 操作正确。
"""

import pytest
from datetime import date, time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from daylife.core.models import (
    Attachment, Base, Category, DailyEntry, ImportMetadata, Tag, entry_tags,
)
from daylife.core.database import DEFAULT_CATEGORIES, init_db
from daylife.core import crud


def _enable_fk(dbapi_conn, connection_record):
    """测试环境中启用 SQLite 外键约束"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ── 测试 fixture ──

@pytest.fixture
def session():
    """创建内存数据库会话，每个测试独立"""
    engine = create_engine("sqlite:///:memory:")
    event.listen(engine, "connect", _enable_fk)
    Base.metadata.create_all(engine)
    sess = sessionmaker(bind=engine)()
    # 预置默认分类
    for cat_data in DEFAULT_CATEGORIES:
        sess.add(Category(**cat_data))
    sess.commit()
    yield sess
    sess.close()


# ══════════════════════════════════════════════════════════════
# 模型测试
# ══════════════════════════════════════════════════════════════


class TestModels:
    """数据模型基本功能测试"""

    def test_create_category(self, session):
        """测试分类创建"""
        categories = session.query(Category).all()
        assert len(categories) == len(DEFAULT_CATEGORIES)
        names = {c.name for c in categories}
        assert "学习" in names
        assert "编程" in names
        assert "社交" in names

    def test_create_entry_basic(self, session):
        """测试基本记录创建"""
        cat = session.query(Category).filter_by(name="学习").first()
        entry = DailyEntry(
            date=date(2026, 3, 21),
            category_id=cat.id,
            content="阅读论文",
            status="completed",
            priority=4,
        )
        session.add(entry)
        session.commit()

        assert entry.id is not None
        assert entry.category.name == "学习"
        assert entry.status == "completed"

    def test_entry_with_time(self, session):
        """测试带时间的记录"""
        entry = DailyEntry(
            date=date(2026, 3, 21),
            content="跑步",
            start_time=time(7, 0),
            end_time=time(8, 30),
            duration_minutes=90,
        )
        session.add(entry)
        session.commit()

        assert entry.start_time == time(7, 0)
        assert entry.end_time == time(8, 30)
        assert entry.duration_minutes == 90

    def test_entry_tags_m2m(self, session):
        """测试记录与标签的多对多关系"""
        entry = DailyEntry(date=date(2026, 3, 21), content="写代码")
        tag1 = Tag(name="Python")
        tag2 = Tag(name="重构")
        entry.tags.extend([tag1, tag2])
        session.add(entry)
        session.commit()

        assert len(entry.tags) == 2
        assert tag1.entries[0].content == "写代码"

    def test_entry_attachments(self, session):
        """测试记录与附件的一对多关系"""
        entry = DailyEntry(date=date(2026, 3, 21), content="截图记录")
        session.add(entry)
        session.flush()

        att = Attachment(
            entry_id=entry.id,
            file_path="/tmp/screenshot.png",
            file_type="image/png",
            file_size=1024,
        )
        session.add(att)
        session.commit()

        assert len(entry.attachments) == 1
        assert entry.attachments[0].file_type == "image/png"

    def test_cascade_delete_entry(self, session):
        """测试删除记录时级联删除附件和标签关联"""
        entry = DailyEntry(date=date(2026, 3, 21), content="临时记录")
        tag = Tag(name="临时")
        entry.tags.append(tag)
        session.add(entry)
        session.flush()

        att = Attachment(entry_id=entry.id, file_path="/tmp/test.txt")
        session.add(att)
        session.commit()
        entry_id = entry.id

        session.delete(entry)
        session.commit()

        # 附件应被级联删除
        assert session.query(Attachment).filter_by(entry_id=entry_id).count() == 0
        # 标签本身仍存在，关联被删除
        assert session.query(Tag).filter_by(name="临时").first() is not None

    def test_import_metadata(self, session):
        """测试导入记录模型"""
        record = ImportMetadata(
            source_file="test.xlsx",
            import_type="excel",
            rows_imported=100,
            rows_skipped=5,
            date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 3, 21),
        )
        session.add(record)
        session.commit()

        assert record.id is not None
        assert record.rows_imported == 100


# ══════════════════════════════════════════════════════════════
# CRUD 操作测试
# ══════════════════════════════════════════════════════════════


class TestCrudEntries:
    """DailyEntry CRUD 测试"""

    def test_create_and_get(self, session):
        """测试创建并获取记录"""
        cat = crud.get_category_by_name(session, "编程")
        entry = crud.create_entry(
            session,
            date=date(2026, 3, 21),
            category_id=cat.id,
            content="实现数据库层",
            status="completed",
            priority=5,
        )
        session.commit()

        fetched = crud.get_entry_by_id(session, entry.id)
        assert fetched is not None
        assert fetched.content == "实现数据库层"
        assert fetched.category.name == "编程"

    def test_get_nonexistent(self, session):
        """获取不存在的记录应返回 None"""
        assert crud.get_entry_by_id(session, 9999) is None

    def test_update_entry(self, session):
        """测试更新记录"""
        entry = crud.create_entry(
            session, date=date(2026, 3, 21), content="原始内容",
        )
        session.commit()

        updated = crud.update_entry(session, entry.id, content="更新后的内容", priority=5)
        session.commit()

        assert updated is not None
        assert updated.content == "更新后的内容"
        assert updated.priority == 5

    def test_update_nonexistent(self, session):
        """更新不存在的记录应返回 None"""
        assert crud.update_entry(session, 9999, content="不存在") is None

    def test_delete_entry(self, session):
        """测试删除记录"""
        entry = crud.create_entry(
            session, date=date(2026, 3, 21), content="待删除",
        )
        session.commit()
        entry_id = entry.id

        assert crud.delete_entry(session, entry_id) is True
        session.commit()
        assert crud.get_entry_by_id(session, entry_id) is None

    def test_delete_nonexistent(self, session):
        """删除不存在的记录应返回 False"""
        assert crud.delete_entry(session, 9999) is False

    def test_get_entries_by_date(self, session):
        """测试按日期获取记录"""
        crud.create_entry(session, date=date(2026, 3, 21), content="任务1")
        crud.create_entry(session, date=date(2026, 3, 21), content="任务2")
        crud.create_entry(session, date=date(2026, 3, 22), content="任务3")
        session.commit()

        entries = crud.get_entries_by_date(session, date(2026, 3, 21))
        assert len(entries) == 2

    def test_get_entries_by_date_range(self, session):
        """测试日期范围查询"""
        crud.create_entry(session, date=date(2026, 3, 20), content="A")
        crud.create_entry(session, date=date(2026, 3, 21), content="B")
        crud.create_entry(session, date=date(2026, 3, 22), content="C")
        crud.create_entry(session, date=date(2026, 3, 25), content="D")
        session.commit()

        entries = crud.get_entries_by_date_range(session, date(2026, 3, 20), date(2026, 3, 22))
        assert len(entries) == 3

    def test_search_by_keyword(self, session):
        """测试关键字搜索"""
        crud.create_entry(session, date=date(2026, 3, 21), content="完成论文初稿")
        crud.create_entry(session, date=date(2026, 3, 21), content="跑步5公里")
        session.commit()

        results = crud.search_entries(session, keyword="论文")
        assert len(results) == 1
        assert "论文" in results[0].content

    def test_search_by_status(self, session):
        """测试按状态筛选"""
        crud.create_entry(session, date=date(2026, 3, 21), content="A", status="completed")
        crud.create_entry(session, date=date(2026, 3, 21), content="B", status="incomplete")
        crud.create_entry(session, date=date(2026, 3, 21), content="C", status="completed")
        session.commit()

        results = crud.search_entries(session, status="completed")
        assert len(results) == 2

    def test_search_pagination(self, session):
        """测试分页查询"""
        for i in range(15):
            crud.create_entry(session, date=date(2026, 3, 21), content=f"记录{i}")
        session.commit()

        page1 = crud.search_entries(session, page=1, page_size=10)
        page2 = crud.search_entries(session, page=2, page_size=10)
        assert len(page1) == 10
        assert len(page2) == 5

    def test_count_entries(self, session):
        """测试记录计数"""
        crud.create_entry(session, date=date(2026, 3, 21), content="A", status="completed")
        crud.create_entry(session, date=date(2026, 3, 21), content="B", status="incomplete")
        session.commit()

        assert crud.count_entries(session) == 2
        assert crud.count_entries(session, status="completed") == 1


class TestCrudCategories:
    """Category CRUD 测试"""

    def test_list_categories(self, session):
        """测试列出所有分类"""
        cats = crud.list_categories(session)
        assert len(cats) == len(DEFAULT_CATEGORIES)

    def test_get_by_name(self, session):
        """测试按名称查找分类"""
        cat = crud.get_category_by_name(session, "科研")
        assert cat is not None
        assert cat.icon == "🔬"

    def test_get_by_name_not_found(self, session):
        """查找不存在的分类应返回 None"""
        assert crud.get_category_by_name(session, "不存在") is None

    def test_create_category(self, session):
        """测试创建自定义分类"""
        cat = crud.create_category(session, name="阅读", icon="📖", color="#FFD700")
        session.commit()
        assert cat.id is not None
        assert crud.get_category_by_name(session, "阅读") is not None

    def test_update_category(self, session):
        """测试更新分类"""
        cat = crud.get_category_by_name(session, "学习")
        updated = crud.update_category(session, cat.id, color="#0000FF")
        session.commit()
        assert updated.color == "#0000FF"


class TestCrudTags:
    """Tag CRUD 测试"""

    def test_get_or_create_tag_new(self, session):
        """测试创建新标签"""
        tag = crud.get_or_create_tag(session, "Python")
        session.commit()
        assert tag.id is not None
        assert tag.name == "Python"

    def test_get_or_create_tag_existing(self, session):
        """测试获取已存在的标签（不会重复创建）"""
        tag1 = crud.get_or_create_tag(session, "测试")
        session.commit()
        tag2 = crud.get_or_create_tag(session, "测试")
        assert tag1.id == tag2.id

    def test_add_tags_to_entry(self, session):
        """测试为记录添加标签"""
        entry = crud.create_entry(session, date=date(2026, 3, 21), content="测试记录")
        crud.add_tags_to_entry(session, entry, ["标签A", "标签B"])
        session.commit()

        assert len(entry.tags) == 2

    def test_set_entry_tags_replace(self, session):
        """测试替换记录标签"""
        entry = crud.create_entry(session, date=date(2026, 3, 21), content="测试记录")
        crud.add_tags_to_entry(session, entry, ["旧标签1", "旧标签2"])
        session.commit()

        crud.set_entry_tags(session, entry, ["新标签"])
        session.commit()

        assert len(entry.tags) == 1
        assert entry.tags[0].name == "新标签"

    def test_popular_tags(self, session):
        """测试高频标签统计"""
        entry1 = crud.create_entry(session, date=date(2026, 3, 21), content="A")
        entry2 = crud.create_entry(session, date=date(2026, 3, 21), content="B")
        entry3 = crud.create_entry(session, date=date(2026, 3, 21), content="C")
        crud.add_tags_to_entry(session, entry1, ["热门", "冷门"])
        crud.add_tags_to_entry(session, entry2, ["热门"])
        crud.add_tags_to_entry(session, entry3, ["热门"])
        session.commit()

        popular = crud.get_popular_tags(session, limit=5)
        assert popular[0]["name"] == "热门"
        assert popular[0]["count"] == 3


class TestCrudAttachments:
    """Attachment CRUD 测试"""

    def test_create_and_get(self, session):
        """测试创建和获取附件"""
        entry = crud.create_entry(session, date=date(2026, 3, 21), content="有附件")
        att = crud.create_attachment(
            session, entry.id, "/tmp/doc.pdf", "application/pdf", 2048,
        )
        session.commit()

        attachments = crud.get_attachments_by_entry(session, entry.id)
        assert len(attachments) == 1
        assert attachments[0].file_path == "/tmp/doc.pdf"

    def test_delete_attachment(self, session):
        """测试删除附件"""
        entry = crud.create_entry(session, date=date(2026, 3, 21), content="有附件")
        att = crud.create_attachment(session, entry.id, "/tmp/test.txt")
        session.commit()

        assert crud.delete_attachment(session, att.id) is True
        session.commit()
        assert crud.get_attachments_by_entry(session, entry.id) == []


class TestCrudImportRecords:
    """ImportMetadata CRUD 测试"""

    def test_create_and_list(self, session):
        """测试创建和列出导入记录"""
        crud.create_import_record(
            session, source_file="data.xlsx", import_type="excel",
            rows_imported=50, date_range_start=date(2026, 1, 1),
            date_range_end=date(2026, 3, 21),
        )
        session.commit()

        records = crud.list_import_records(session)
        assert len(records) == 1
        assert records[0].rows_imported == 50


class TestDatabaseInit:
    """数据库初始化测试"""

    def test_init_db_creates_tables_and_categories(self):
        """测试 init_db 自动建表并插入默认分类"""
        engine = create_engine("sqlite:///:memory:")
        session = init_db(engine)

        categories = session.query(Category).all()
        assert len(categories) == len(DEFAULT_CATEGORIES)
        names = {c.name for c in categories}
        assert "编程" in names
        assert "社交" in names
        session.close()

    def test_init_db_idempotent(self):
        """测试 init_db 多次调用不会重复插入分类"""
        engine = create_engine("sqlite:///:memory:")
        init_db(engine)
        session = init_db(engine)

        categories = session.query(Category).all()
        assert len(categories) == len(DEFAULT_CATEGORIES)
        session.close()
