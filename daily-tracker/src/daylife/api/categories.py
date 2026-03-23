"""分类路由"""

from fastapi import APIRouter, Depends

from daylife.core.database import get_session
from daylife.core.schemas import CategoryOut
from daylife.core.service import DaylifeService

router = APIRouter()


def get_service():
    session = get_session()
    try:
        yield DaylifeService(session)
    finally:
        session.close()


@router.get("", response_model=list[CategoryOut])
def list_categories(service: DaylifeService = Depends(get_service)):
    return service.list_categories()
