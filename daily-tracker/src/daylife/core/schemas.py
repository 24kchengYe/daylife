"""Pydantic 数据校验模型"""

from datetime import date, datetime, time
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# ══════════════════════════════════════════════════════════════
# 统一响应模型
# ══════════════════════════════════════════════════════════════


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = 0
    message: str = "ok"
    data: T | None = None


class PaginatedData(BaseModel, Generic[T]):
    """分页数据包装"""
    items: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    pages: int = 0


# ══════════════════════════════════════════════════════════════
# 分类
# ══════════════════════════════════════════════════════════════


class CategoryOut(BaseModel):
    id: int
    name: str
    icon: str | None = None
    color: str | None = None
    sort_order: int = 0

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str
    icon: str | None = None
    color: str | None = None
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    color: str | None = None
    sort_order: int | None = None


# ══════════════════════════════════════════════════════════════
# 标签
# ══════════════════════════════════════════════════════════════


class TagOut(BaseModel):
    id: int
    name: str
    color: str | None = None

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════
# 活动记录
# ══════════════════════════════════════════════════════════════


class EntryCreate(BaseModel):
    date: date
    category: str | None = None
    content: str
    status: str = "completed"
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = None
    priority: int = Field(default=3, ge=1, le=5)
    tags: list[str] = []
    notes: str | None = None
    source: str = "web"


class EntryUpdate(BaseModel):
    category: str | None = None
    content: str | None = None
    status: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = None
    priority: int | None = None
    tags: list[str] | None = None
    notes: str | None = None


class EntryOut(BaseModel):
    id: int
    date: date
    category: CategoryOut | None = None
    content: str
    status: str | None = None
    start_time: time | None = None
    end_time: time | None = None
    duration_minutes: int | None = None
    priority: int | None = None
    tags: list[TagOut] = []
    notes: str | None = None
    source: str | None = None
    data_json: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class EntryQuery(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    category: str | None = None
    status: str | None = None
    keyword: str | None = None
    tags: list[str] | None = None
    page: int = 1
    page_size: int = 20


# ══════════════════════════════════════════════════════════════
# 统计
# ══════════════════════════════════════════════════════════════


class HeatmapItem(BaseModel):
    date: date
    count: int
    completed: int
    total_minutes: int | None = None


class CategoryStat(BaseModel):
    category: str
    icon: str | None = None
    color: str | None = None
    count: int
    total_minutes: int | None = None
    completion_rate: float


class StatsOverview(BaseModel):
    total_entries: int
    total_days: int
    completion_rate: float
    most_active_category: str | None = None
    streak_days: int = 0


class ImportMetadataOut(BaseModel):
    id: int
    source_file: str
    import_type: str
    rows_imported: int
    rows_skipped: int
    date_range_start: date | None = None
    date_range_end: date | None = None
    imported_at: datetime | None = None
    notes: str | None = None

    model_config = {"from_attributes": True}
