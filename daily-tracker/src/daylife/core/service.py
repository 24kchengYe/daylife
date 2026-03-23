"""业务服务层 - CRUD + 统计"""

from datetime import date

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload

from daylife.core.models import Category, DailyEntry, Tag, entry_tags
from daylife.core.schemas import EntryCreate, EntryQuery, EntryUpdate


class DaylifeService:
    def __init__(self, session: Session):
        self.session = session

    # ── Entries CRUD ──

    def create_entry(self, data: EntryCreate) -> DailyEntry:
        entry = DailyEntry(
            date=data.date,
            content=data.content,
            status=data.status,
            start_time=data.start_time,
            end_time=data.end_time,
            duration_minutes=data.duration_minutes,
            priority=data.priority,
            notes=data.notes,
            source=data.source,
        )

        if data.category:
            cat = self.session.query(Category).filter_by(name=data.category).first()
            if cat:
                entry.category_id = cat.id

        self.session.add(entry)
        self.session.flush()

        for tag_name in data.tags:
            tag = self.session.query(Tag).filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                self.session.add(tag)
                self.session.flush()
            entry.tags.append(tag)
        self.session.commit()
        self.session.refresh(entry)
        return entry

    def get_entry(self, entry_id: int) -> DailyEntry | None:
        return (
            self.session.query(DailyEntry)
            .options(joinedload(DailyEntry.category), joinedload(DailyEntry.tags))
            .filter_by(id=entry_id)
            .first()
        )

    def update_entry(self, entry_id: int, data: EntryUpdate) -> DailyEntry | None:
        entry = self.get_entry(entry_id)
        if not entry:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "category" and value is not None:
                cat = self.session.query(Category).filter_by(name=value).first()
                if cat:
                    entry.category_id = cat.id
            elif field == "tags" and value is not None:
                entry.tags.clear()
                for tag_name in value:
                    tag = self.session.query(Tag).filter_by(name=tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        self.session.add(tag)
                        self.session.flush()
                    entry.tags.append(tag)
            elif field not in ("category", "tags"):
                setattr(entry, field, value)

        self.session.commit()
        self.session.refresh(entry)
        return entry

    def delete_entry(self, entry_id: int) -> bool:
        entry = self.session.query(DailyEntry).filter_by(id=entry_id).first()
        if not entry:
            return False
        self.session.delete(entry)
        self.session.commit()
        return True

    def query_entries(self, query: EntryQuery) -> list[DailyEntry]:
        q = (
            self.session.query(DailyEntry)
            .options(joinedload(DailyEntry.category), joinedload(DailyEntry.tags))
        )

        if query.date_from:
            q = q.filter(DailyEntry.date >= query.date_from)
        if query.date_to:
            q = q.filter(DailyEntry.date <= query.date_to)
        if query.category:
            q = q.join(Category).filter(Category.name == query.category)
        if query.status:
            q = q.filter(DailyEntry.status == query.status)
        if query.keyword:
            q = q.filter(DailyEntry.content.contains(query.keyword))

        q = q.order_by(DailyEntry.date.desc(), DailyEntry.created_at.desc())

        offset = (query.page - 1) * query.page_size
        return q.offset(offset).limit(query.page_size).all()

    def get_entries_by_date(self, target_date: date) -> list[DailyEntry]:
        return (
            self.session.query(DailyEntry)
            .options(joinedload(DailyEntry.category), joinedload(DailyEntry.tags))
            .filter(DailyEntry.date == target_date)
            .order_by(DailyEntry.start_time, DailyEntry.created_at)
            .all()
        )

    # ── Categories ──

    def list_categories(self) -> list[Category]:
        return self.session.query(Category).order_by(Category.sort_order).all()

    # ── Stats ──

    def get_heatmap_data(self, date_from: date, date_to: date) -> list[dict]:
        rows = (
            self.session.query(
                DailyEntry.date,
                func.count(DailyEntry.id).label("count"),
                func.sum(
                    case((DailyEntry.status == "completed", 1), else_=0)
                ).label("completed"),
                func.sum(DailyEntry.duration_minutes).label("total_minutes"),
            )
            .filter(DailyEntry.date >= date_from, DailyEntry.date <= date_to)
            .group_by(DailyEntry.date)
            .all()
        )
        return [
            {
                "date": row.date,
                "count": row.count,
                "completed": row.completed or 0,
                "total_minutes": row.total_minutes,
            }
            for row in rows
        ]

    def get_overview(self) -> dict:
        total = self.session.query(func.count(DailyEntry.id)).scalar() or 0
        completed = (
            self.session.query(func.count(DailyEntry.id))
            .filter(DailyEntry.status == "completed")
            .scalar()
            or 0
        )
        total_days = (
            self.session.query(func.count(func.distinct(DailyEntry.date))).scalar() or 0
        )

        return {
            "total_entries": total,
            "total_days": total_days,
            "completion_rate": (completed / total * 100) if total > 0 else 0,
        }
