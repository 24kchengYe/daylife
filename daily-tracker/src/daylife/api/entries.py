"""活动记录路由"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from daylife.core.database import get_session
from daylife.core.schemas import EntryCreate, EntryOut, EntryQuery, EntryUpdate
from daylife.core.service import DaylifeService

router = APIRouter()


def get_service():
    session = get_session()
    try:
        yield DaylifeService(session)
    finally:
        session.close()


@router.get("/today", response_model=list[EntryOut])
def get_today(service: DaylifeService = Depends(get_service)):
    return service.get_entries_by_date(date.today())


@router.get("/date/{target_date}", response_model=list[EntryOut])
def get_by_date(target_date: date, service: DaylifeService = Depends(get_service)):
    return service.get_entries_by_date(target_date)


@router.get("", response_model=list[EntryOut])
def list_entries(
    date_from: date | None = None,
    date_to: date | None = None,
    category: str | None = None,
    status: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    service: DaylifeService = Depends(get_service),
):
    query = EntryQuery(
        date_from=date_from,
        date_to=date_to,
        category=category,
        status=status,
        keyword=keyword,
        page=page,
        page_size=page_size,
    )
    return service.query_entries(query)


@router.get("/{entry_id}", response_model=EntryOut)
def get_entry(entry_id: int, service: DaylifeService = Depends(get_service)):
    entry = service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.post("", response_model=EntryOut, status_code=201)
def create_entry(data: EntryCreate, service: DaylifeService = Depends(get_service)):
    return service.create_entry(data)


@router.put("/{entry_id}", response_model=EntryOut)
def update_entry(
    entry_id: int, data: EntryUpdate, service: DaylifeService = Depends(get_service)
):
    entry = service.update_entry(entry_id, data)
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    return entry


@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: int, service: DaylifeService = Depends(get_service)):
    if not service.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail="Entry not found")
