"""SQLAlchemy 数据模型定义"""

from datetime import date, datetime, time

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    Time,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# 多对多关联表：entry <-> tag（打上的标签）
entry_tags = Table(
    "entry_tags",
    Base.metadata,
    Column("entry_id", Integer, ForeignKey("daily_entries.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

# 记录 AI 扫描过的 entry（无论是否打上标签）
tag_scanned = Table(
    "tag_scanned",
    Base.metadata,
    Column("entry_id", Integer, ForeignKey("daily_entries.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    icon: Mapped[str | None] = mapped_column(String(10))
    color: Mapped[str | None] = mapped_column(String(7))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entries: Mapped[list["DailyEntry"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category {self.icon} {self.name}>"


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    color: Mapped[str | None] = mapped_column(String(7))
    description: Mapped[str | None] = mapped_column(Text)

    entries: Mapped[list["DailyEntry"]] = relationship(
        secondary=entry_tags, back_populates="tags"
    )

    def __repr__(self) -> str:
        return f"<Tag {self.name}>"


class DailyEntry(Base):
    __tablename__ = "daily_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str | None] = mapped_column(String(20), default="completed")
    start_time: Mapped[time | None] = mapped_column(Time)
    end_time: Mapped[time | None] = mapped_column(Time)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    priority: Mapped[int | None] = mapped_column(Integer, default=3)
    notes: Mapped[str | None] = mapped_column(Text)
    data_json: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(20), default="cli")
    ai_classified: Mapped[int] = mapped_column(Integer, default=0)  # 0=未分类, 1=已AI分类
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    category: Mapped[Category | None] = relationship(back_populates="entries")
    tags: Mapped[list[Tag]] = relationship(secondary=entry_tags, back_populates="entries")
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan", passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<DailyEntry {self.date} {self.content[:30]}>"


class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("daily_entries.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(50))
    file_size: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    entry: Mapped[DailyEntry] = relationship(back_populates="attachments")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    period_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "week" | "month" | "year"
    period_key: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)  # "2026-W12" | "2026-03" | "2026"
    date_from: Mapped[date] = mapped_column(Date, nullable=False)
    date_to: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown
    model_used: Mapped[str | None] = mapped_column(String(100))
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    formatted: Mapped[int] = mapped_column(Integer, default=0)  # 0=未格式化, 1=已格式化
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Report {self.period_type} {self.period_key}>"


class ImportMetadata(Base):
    __tablename__ = "import_metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_file: Mapped[str] = mapped_column(Text, nullable=False)
    import_type: Mapped[str] = mapped_column(String(20), nullable=False)
    rows_imported: Mapped[int] = mapped_column(Integer, default=0)
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0)
    date_range_start: Mapped[date | None] = mapped_column(Date)
    date_range_end: Mapped[date | None] = mapped_column(Date)
    color_mapping: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text)
