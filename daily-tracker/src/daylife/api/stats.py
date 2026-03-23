"""统计路由"""

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from daylife.core.database import get_session
from daylife.core.schemas import HeatmapItem
from daylife.core.service import DaylifeService

router = APIRouter()


def get_service():
    session = get_session()
    try:
        yield DaylifeService(session)
    finally:
        session.close()


@router.get("/overview")
def get_overview(service: DaylifeService = Depends(get_service)):
    return service.get_overview()


@router.get("/heatmap", response_model=list[HeatmapItem])
def get_heatmap(
    date_from: date | None = None,
    date_to: date | None = None,
    service: DaylifeService = Depends(get_service),
):
    if date_to is None:
        date_to = date.today()
    if date_from is None:
        date_from = date_to - timedelta(days=365)
    return service.get_heatmap_data(date_from, date_to)
