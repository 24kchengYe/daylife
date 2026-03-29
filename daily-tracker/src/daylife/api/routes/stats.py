"""统计路由 - 多维度统计分析"""

from datetime import date, timedelta

from fastapi import APIRouter, Query

from daylife.core.database import get_session
from daylife.core.schemas import ApiResponse
from daylife.core.stats_service import StatsService

router = APIRouter()


@router.get("/daily", response_model=ApiResponse)
def get_daily_stats(
    date: date | None = Query(None, description="日期，默认今天"),
):
    target = date or __import__("datetime").date.today()
    session = get_session()
    try:
        svc = StatsService(session)
        data = svc.get_daily_summary(target)
        # date 对象序列化为字符串
        data["date"] = data["date"].isoformat()
        return ApiResponse(data=data)
    finally:
        session.close()


@router.get("/heatmap", response_model=ApiResponse)
def get_heatmap(
    year: int | None = Query(None, description="年份，默认今年"),
):
    from datetime import date as date_cls
    y = year or date_cls.today().year
    date_from = date_cls(y, 1, 1)
    date_to = date_cls(y, 12, 31)

    session = get_session()
    try:
        svc = StatsService(session)
        items = svc.get_heatmap_data(date_from, date_to)
        # 转换 date 对象
        for item in items:
            item["date"] = item["date"].isoformat()
        return ApiResponse(data=items)
    finally:
        session.close()


@router.get("/heatmap-detail", response_model=ApiResponse)
def get_heatmap_detail(
    year: int | None = Query(None, description="年份，默认今年"),
):
    """轻量版热力图：按分类聚合，不返回 content（KB 级响应替代 MB 级）"""
    from datetime import date as date_cls
    y = year or date_cls.today().year
    date_from = date_cls(y, 1, 1)
    date_to = date_cls(y, 12, 31)

    session = get_session()
    try:
        svc = StatsService(session)
        items = svc.get_heatmap_by_category(date_from, date_to)
        for item in items:
            item["date"] = item["date"].isoformat()
        return ApiResponse(data=items)
    finally:
        session.close()


@router.get("/category", response_model=ApiResponse)
def get_category_stats(
    start: date | None = Query(None, description="起始日期"),
    end: date | None = Query(None, description="截止日期"),
):
    from datetime import date as date_cls
    today = date_cls.today()
    d_end = end or today
    d_start = start or (today - timedelta(days=30))

    session = get_session()
    try:
        svc = StatsService(session)
        data = svc.get_category_distribution(d_start, d_end)
        return ApiResponse(data=data)
    finally:
        session.close()


@router.get("/trend", response_model=ApiResponse)
def get_trend(
    start: date | None = Query(None, description="起始日期"),
    end: date | None = Query(None, description="截止日期"),
    interval: str = Query("week", description="聚合粒度: day/week/month"),
):
    from datetime import date as date_cls
    today = date_cls.today()
    d_end = end or today
    d_start = start or (today - timedelta(days=90))

    session = get_session()
    try:
        svc = StatsService(session)
        data = svc.get_trend_data(d_start, d_end, group_by=interval)
        # 序列化 date 对象
        for item in data:
            for key in ("date", "week_start"):
                if key in item and hasattr(item[key], "isoformat"):
                    item[key] = item[key].isoformat()
        return ApiResponse(data=data)
    finally:
        session.close()


@router.get("/completion", response_model=ApiResponse)
def get_completion(
    start: date | None = Query(None, description="起始日期"),
    end: date | None = Query(None, description="截止日期"),
):
    from datetime import date as date_cls
    today = date_cls.today()
    d_end = end or today
    d_start = start or (today - timedelta(days=90))

    session = get_session()
    try:
        svc = StatsService(session)
        data = svc.get_completion_rate_by_category(d_start, d_end)
        return ApiResponse(data=data)
    finally:
        session.close()


@router.get("/streak", response_model=ApiResponse)
def get_streak():
    session = get_session()
    try:
        svc = StatsService(session)
        current = svc.get_current_streak()
        longest = svc.get_longest_streak()
        # 序列化 date 对象
        if longest.get("start") and hasattr(longest["start"], "isoformat"):
            longest["start"] = longest["start"].isoformat()
        if longest.get("end") and hasattr(longest["end"], "isoformat"):
            longest["end"] = longest["end"].isoformat()
        return ApiResponse(data={
            "current_streak": current,
            "longest_streak": longest,
        })
    finally:
        session.close()


@router.get("/yearly-summary", response_model=ApiResponse)
def get_yearly_summary(
    year: int | None = Query(None, description="年份，默认今年"),
):
    from datetime import date as date_cls
    y = year or date_cls.today().year

    session = get_session()
    try:
        svc = StatsService(session)
        data = svc.get_yearly_summary(y)
        return ApiResponse(data=data)
    finally:
        session.close()
