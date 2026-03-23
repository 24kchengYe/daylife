"""服务层测试"""

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from daylife.core.database import DEFAULT_CATEGORIES
from daylife.core.models import Base, Category
from daylife.core.schemas import EntryCreate
from daylife.core.service import DaylifeService


def _setup():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    for cat_data in DEFAULT_CATEGORIES:
        session.add(Category(**cat_data))
    session.commit()
    return session


def test_create_and_query():
    session = _setup()
    service = DaylifeService(session)

    entry = service.create_entry(
        EntryCreate(
            date=date(2026, 3, 21),
            category="科研",
            content="完成论文初稿",
            tags=["论文", "写作"],
            priority=5,
        )
    )

    assert entry.id is not None
    assert entry.category.name == "科研"
    assert len(entry.tags) == 2

    entries = service.get_entries_by_date(date(2026, 3, 21))
    assert len(entries) == 1
    session.close()


def test_overview_stats():
    session = _setup()
    service = DaylifeService(session)

    service.create_entry(EntryCreate(date=date(2026, 3, 21), content="任务1", status="completed"))
    service.create_entry(EntryCreate(date=date(2026, 3, 21), content="任务2", status="incomplete"))

    overview = service.get_overview()
    assert overview["total_entries"] == 2
    assert overview["completion_rate"] == 50.0
    session.close()
