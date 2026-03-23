"""活动记录路由 - 完整 CRUD + 搜索"""

from datetime import date

from fastapi import APIRouter, Query

from daylife.core.database import get_session
from daylife.core.entry_service import EntryService
from daylife.core.schemas import (
    ApiResponse,
    EntryCreate,
    EntryOut,
    EntryQuery,
    EntryUpdate,
    PaginatedData,
)

router = APIRouter()


def _entry_to_out(entry) -> EntryOut:
    return EntryOut.model_validate(entry)


@router.get("", response_model=ApiResponse[PaginatedData[EntryOut]])
def list_entries(
    date: date | None = Query(None, description="精确日期"),
    start: date | None = Query(None, description="起始日期"),
    end: date | None = Query(None, description="截止日期"),
    category: str | None = Query(None, description="分类名"),
    status: str | None = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100000),
):
    session = get_session()
    try:
        svc = EntryService(session)
        # 精确日期查询
        if date is not None:
            entries = svc.get_entries_by_date(date)
            items = [_entry_to_out(e) for e in entries]
            return ApiResponse(data=PaginatedData(
                items=items, total=len(items), page=1, page_size=limit, pages=1,
            ))

        query = EntryQuery(
            date_from=start, date_to=end, category=category,
            status=status, page=page, page_size=limit,
        )
        entries = svc.search(query)
        items = [_entry_to_out(e) for e in entries]

        # 计算总数（简化：用 crud 的 count_entries）
        from daylife.core import crud
        total = crud.count_entries(session, date_from=start, date_to=end, status=status)
        pages = (total + limit - 1) // limit if total > 0 else 0

        return ApiResponse(data=PaginatedData(
            items=items, total=total, page=page, page_size=limit, pages=pages,
        ))
    finally:
        session.close()


@router.post("", response_model=ApiResponse[EntryOut])
def create_entry(data: EntryCreate):
    session = get_session()
    try:
        svc = EntryService(session)
        entry = svc.add_entry(data)
        return ApiResponse(data=_entry_to_out(entry))
    finally:
        session.close()


@router.put("/{entry_id}", response_model=ApiResponse[EntryOut])
def update_entry(entry_id: int, data: EntryUpdate):
    session = get_session()
    try:
        svc = EntryService(session)
        entry = svc.update_entry(entry_id, data)
        if not entry:
            return ApiResponse(code=404, message="Entry not found")
        return ApiResponse(data=_entry_to_out(entry))
    finally:
        session.close()


@router.delete("/{entry_id}", response_model=ApiResponse)
def delete_entry(entry_id: int):
    session = get_session()
    try:
        svc = EntryService(session)
        if not svc.delete_entry(entry_id):
            return ApiResponse(code=404, message="Entry not found")
        return ApiResponse(message="Deleted")
    finally:
        session.close()


@router.get("/search", response_model=ApiResponse[list[EntryOut]])
def search_entries(
    q: str = Query(..., description="搜索关键词"),
    limit: int = Query(20, ge=1, le=100000),
):
    session = get_session()
    try:
        svc = EntryService(session)
        query = EntryQuery(keyword=q, page=1, page_size=limit)
        entries = svc.search(query)
        items = [_entry_to_out(e) for e in entries]
        return ApiResponse(data=items)
    finally:
        session.close()
