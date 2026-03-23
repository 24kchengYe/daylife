"""数据模型测试"""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from daylife.core.models import Base, Category, DailyEntry, Tag


def test_create_entry():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    cat = Category(name="学习", icon="📚", color="#4A90D9")
    session.add(cat)
    session.flush()

    entry = DailyEntry(
        date=date(2026, 3, 21),
        category_id=cat.id,
        content="测试记录",
        status="completed",
    )
    session.add(entry)
    session.commit()

    assert entry.id is not None
    assert entry.category.name == "学习"
    session.close()


def test_entry_tags():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    entry = DailyEntry(date=date(2026, 3, 21), content="带标签的记录")
    tag1 = Tag(name="论文")
    tag2 = Tag(name="写作")
    entry.tags.extend([tag1, tag2])
    session.add(entry)
    session.commit()

    assert len(entry.tags) == 2
    assert entry.tags[0].name == "论文"
    session.close()
