"""统计服务层 - 日/周/月/年汇总、完成率、分类占比、连续天数等

提供多维度的活动数据统计分析功能。
"""

from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import case, distinct, func
from sqlalchemy.orm import Session

from daylife.core.models import Category, DailyEntry, Tag, entry_tags


class StatsService:
    """统计分析服务"""

    def __init__(self, session: Session):
        self.session = session

    # ══════════════════════════════════════════════════════════════
    # 总览统计
    # ══════════════════════════════════════════════════════════════

    def get_overview(self, date_from: date | None = None, date_to: date | None = None) -> dict:
        """获取总览统计：总记录数、完成率、活跃天数、最活跃分类

        Args:
            date_from: 起始日期，None 表示不限
            date_to:   截止日期，None 表示不限
        """
        q = self.session.query(DailyEntry)
        if date_from:
            q = q.filter(DailyEntry.date >= date_from)
        if date_to:
            q = q.filter(DailyEntry.date <= date_to)

        total = q.count()
        completed = q.filter(DailyEntry.status == "completed").count()
        active_days = (
            q.with_entities(func.count(distinct(DailyEntry.date))).scalar() or 0
        )
        total_minutes = q.with_entities(func.sum(DailyEntry.duration_minutes)).scalar() or 0

        # 最活跃分类
        most_active = (
            q.with_entities(DailyEntry.category_id, func.count(DailyEntry.id).label("cnt"))
            .group_by(DailyEntry.category_id)
            .order_by(func.count(DailyEntry.id).desc())
            .first()
        )
        most_active_name = None
        if most_active and most_active.category_id:
            cat = self.session.get(Category, most_active.category_id)
            if cat:
                most_active_name = cat.name

        return {
            "total_entries": total,
            "completed_entries": completed,
            "total_days": active_days,
            "total_minutes": total_minutes,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "most_active_category": most_active_name,
            "streak_days": self.get_current_streak(),
        }

    # ══════════════════════════════════════════════════════════════
    # 日/周/月/年汇总
    # ══════════════════════════════════════════════════════════════

    def get_daily_summary(self, target_date: date) -> dict:
        """获取某一天的活动汇总"""
        entries = (
            self.session.query(DailyEntry)
            .filter(DailyEntry.date == target_date)
            .all()
        )
        total = len(entries)
        completed = sum(1 for e in entries if e.status == "completed")
        total_minutes = sum(e.duration_minutes or 0 for e in entries)

        # 按分类分组
        by_category: dict[str, int] = defaultdict(int)
        for e in entries:
            cat_name = e.category.name if e.category else "其他"
            by_category[cat_name] += 1

        return {
            "date": target_date,
            "total": total,
            "completed": completed,
            "incomplete": total - completed,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "total_minutes": total_minutes,
            "by_category": dict(by_category),
        }

    def get_weekly_summary(self, week_start: date | None = None) -> dict:
        """获取一周的活动汇总

        Args:
            week_start: 周一日期，默认为本周一
        """
        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        entries = (
            self.session.query(DailyEntry)
            .filter(DailyEntry.date >= week_start, DailyEntry.date <= week_end)
            .all()
        )
        total = len(entries)
        completed = sum(1 for e in entries if e.status == "completed")
        active_days = len({e.date for e in entries})
        total_minutes = sum(e.duration_minutes or 0 for e in entries)

        # 每日统计
        daily_counts: dict[str, int] = {}
        for i in range(7):
            d = week_start + timedelta(days=i)
            daily_counts[d.isoformat()] = sum(1 for e in entries if e.date == d)

        return {
            "week_start": week_start,
            "week_end": week_end,
            "total": total,
            "completed": completed,
            "active_days": active_days,
            "total_minutes": total_minutes,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "daily_counts": daily_counts,
        }

    def get_monthly_summary(self, year: int, month: int) -> dict:
        """获取月度活动汇总"""
        month_start = date(year, month, 1)
        # 计算月末
        if month == 12:
            month_end = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(year, month + 1, 1) - timedelta(days=1)

        entries = (
            self.session.query(DailyEntry)
            .filter(DailyEntry.date >= month_start, DailyEntry.date <= month_end)
            .all()
        )
        total = len(entries)
        completed = sum(1 for e in entries if e.status == "completed")
        active_days = len({e.date for e in entries})
        total_minutes = sum(e.duration_minutes or 0 for e in entries)

        return {
            "year": year,
            "month": month,
            "total": total,
            "completed": completed,
            "active_days": active_days,
            "total_days": (month_end - month_start).days + 1,
            "total_minutes": total_minutes,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
        }

    def get_yearly_summary(self, year: int) -> dict:
        """获取年度活动汇总"""
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        entries = (
            self.session.query(DailyEntry)
            .filter(DailyEntry.date >= year_start, DailyEntry.date <= year_end)
            .all()
        )
        total = len(entries)
        completed = sum(1 for e in entries if e.status == "completed")
        active_days = len({e.date for e in entries})
        total_minutes = sum(e.duration_minutes or 0 for e in entries)

        # 按月统计
        monthly: dict[int, int] = defaultdict(int)
        for e in entries:
            monthly[e.date.month] += 1

        return {
            "year": year,
            "total": total,
            "completed": completed,
            "active_days": active_days,
            "total_minutes": total_minutes,
            "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            "monthly_counts": dict(monthly),
        }

    # ══════════════════════════════════════════════════════════════
    # 完成率统计
    # ══════════════════════════════════════════════════════════════

    def get_completion_rate_by_category(
        self, date_from: date, date_to: date,
    ) -> list[dict]:
        """按分类计算完成率"""
        rows = (
            self.session.query(
                Category.name,
                Category.icon,
                Category.color,
                func.count(DailyEntry.id).label("total"),
                func.sum(
                    case((DailyEntry.status == "completed", 1), else_=0)
                ).label("completed"),
                func.sum(DailyEntry.duration_minutes).label("total_minutes"),
            )
            .join(DailyEntry, DailyEntry.category_id == Category.id)
            .filter(DailyEntry.date >= date_from, DailyEntry.date <= date_to)
            .group_by(Category.id)
            .order_by(func.count(DailyEntry.id).desc())
            .all()
        )
        return [
            {
                "category": r.name,
                "icon": r.icon,
                "color": r.color,
                "count": r.total,
                "completed": r.completed or 0,
                "total_minutes": r.total_minutes or 0,
                "completion_rate": round((r.completed or 0) / r.total * 100, 1) if r.total else 0,
            }
            for r in rows
        ]

    def get_completion_rate_by_week(self, weeks: int = 12) -> list[dict]:
        """按周计算完成率趋势（最近 N 周）"""
        today = date.today()
        result = []
        for i in range(weeks - 1, -1, -1):
            week_start = today - timedelta(days=today.weekday() + 7 * i)
            week_end = week_start + timedelta(days=6)

            total = (
                self.session.query(func.count(DailyEntry.id))
                .filter(DailyEntry.date >= week_start, DailyEntry.date <= week_end)
                .scalar() or 0
            )
            completed = (
                self.session.query(func.count(DailyEntry.id))
                .filter(
                    DailyEntry.date >= week_start, DailyEntry.date <= week_end,
                    DailyEntry.status == "completed",
                )
                .scalar() or 0
            )
            result.append({
                "week_start": week_start,
                "week_end": week_end,
                "total": total,
                "completed": completed,
                "completion_rate": round(completed / total * 100, 1) if total > 0 else 0,
            })
        return result

    # ══════════════════════════════════════════════════════════════
    # 分类占比
    # ══════════════════════════════════════════════════════════════

    def get_category_distribution(self, date_from: date, date_to: date) -> list[dict]:
        """获取分类占比（按数量和时长）"""
        rows = (
            self.session.query(
                Category.name,
                Category.icon,
                Category.color,
                func.count(DailyEntry.id).label("count"),
                func.sum(DailyEntry.duration_minutes).label("minutes"),
            )
            .join(DailyEntry, DailyEntry.category_id == Category.id)
            .filter(DailyEntry.date >= date_from, DailyEntry.date <= date_to)
            .group_by(Category.id)
            .order_by(func.count(DailyEntry.id).desc())
            .all()
        )
        total_count = sum(r.count for r in rows) or 1
        total_minutes = sum(r.minutes or 0 for r in rows) or 1

        return [
            {
                "category": r.name,
                "icon": r.icon,
                "color": r.color,
                "count": r.count,
                "count_ratio": round(r.count / total_count * 100, 1),
                "minutes": r.minutes or 0,
                "minutes_ratio": round((r.minutes or 0) / total_minutes * 100, 1),
            }
            for r in rows
        ]

    # ══════════════════════════════════════════════════════════════
    # 热力图数据
    # ══════════════════════════════════════════════════════════════

    def get_heatmap_data(self, date_from: date, date_to: date) -> list[dict]:
        """获取日历热力图数据（每日活动数量、完成数、总时长）"""
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
            .order_by(DailyEntry.date)
            .all()
        )
        return [
            {
                "date": r.date,
                "count": r.count,
                "completed": r.completed or 0,
                "total_minutes": r.total_minutes or 0,
            }
            for r in rows
        ]

    # ══════════════════════════════════════════════════════════════
    # 趋势分析
    # ══════════════════════════════════════════════════════════════

    def get_trend_data(self, date_from: date, date_to: date, group_by: str = "day") -> list[dict]:
        """获取活动量趋势数据

        Args:
            group_by: 聚合粒度 - "day" / "week" / "month"
        """
        entries = (
            self.session.query(DailyEntry)
            .filter(DailyEntry.date >= date_from, DailyEntry.date <= date_to)
            .all()
        )

        if group_by == "day":
            return self._trend_by_day(entries, date_from, date_to)
        elif group_by == "week":
            return self._trend_by_week(entries)
        elif group_by == "month":
            return self._trend_by_month(entries)
        return []

    def _trend_by_day(self, entries: list[DailyEntry], date_from: date, date_to: date) -> list[dict]:
        """按天聚合趋势"""
        counts: dict[date, dict] = {}
        current = date_from
        while current <= date_to:
            counts[current] = {"date": current, "count": 0, "completed": 0, "minutes": 0}
            current += timedelta(days=1)

        for e in entries:
            if e.date in counts:
                counts[e.date]["count"] += 1
                if e.status == "completed":
                    counts[e.date]["completed"] += 1
                counts[e.date]["minutes"] += e.duration_minutes or 0

        return list(counts.values())

    def _trend_by_week(self, entries: list[DailyEntry]) -> list[dict]:
        """按周聚合趋势"""
        weeks: dict[date, dict] = defaultdict(
            lambda: {"count": 0, "completed": 0, "minutes": 0}
        )
        for e in entries:
            week_start = e.date - timedelta(days=e.date.weekday())
            weeks[week_start]["count"] += 1
            if e.status == "completed":
                weeks[week_start]["completed"] += 1
            weeks[week_start]["minutes"] += e.duration_minutes or 0

        return [
            {"week_start": k, **v}
            for k, v in sorted(weeks.items())
        ]

    def _trend_by_month(self, entries: list[DailyEntry]) -> list[dict]:
        """按月聚合趋势"""
        months: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "completed": 0, "minutes": 0}
        )
        for e in entries:
            key = f"{e.date.year}-{e.date.month:02d}"
            months[key]["count"] += 1
            if e.status == "completed":
                months[key]["completed"] += 1
            months[key]["minutes"] += e.duration_minutes or 0

        return [
            {"month": k, **v}
            for k, v in sorted(months.items())
        ]

    # ══════════════════════════════════════════════════════════════
    # 连续天数统计
    # ══════════════════════════════════════════════════════════════

    def get_current_streak(self) -> int:
        """计算从今天往前的连续活跃天数

        如果今天没有记录，从昨天开始计算。
        """
        # 获取所有有记录的日期（降序）
        dates = (
            self.session.query(distinct(DailyEntry.date))
            .order_by(DailyEntry.date.desc())
            .all()
        )
        if not dates:
            return 0

        active_dates = {d[0] for d in dates}
        today = date.today()

        # 从今天或昨天开始
        current = today if today in active_dates else today - timedelta(days=1)
        if current not in active_dates:
            return 0

        streak = 0
        while current in active_dates:
            streak += 1
            current -= timedelta(days=1)

        return streak

    def get_longest_streak(self) -> dict:
        """计算历史最长连续活跃天数"""
        dates = (
            self.session.query(distinct(DailyEntry.date))
            .order_by(DailyEntry.date)
            .all()
        )
        if not dates:
            return {"days": 0, "start": None, "end": None}

        sorted_dates = sorted(d[0] for d in dates)
        max_streak = 1
        max_start = sorted_dates[0]
        max_end = sorted_dates[0]
        current_streak = 1
        current_start = sorted_dates[0]

        for i in range(1, len(sorted_dates)):
            if sorted_dates[i] - sorted_dates[i - 1] == timedelta(days=1):
                current_streak += 1
            else:
                if current_streak > max_streak:
                    max_streak = current_streak
                    max_start = current_start
                    max_end = sorted_dates[i - 1]
                current_streak = 1
                current_start = sorted_dates[i]

        # 检查最后一段
        if current_streak > max_streak:
            max_streak = current_streak
            max_start = current_start
            max_end = sorted_dates[-1]

        return {"days": max_streak, "start": max_start, "end": max_end}

    # ══════════════════════════════════════════════════════════════
    # 标签统计
    # ══════════════════════════════════════════════════════════════

    def get_tag_frequency(self, limit: int = 30) -> list[dict]:
        """获取标签使用频次（标签云数据）"""
        rows = (
            self.session.query(
                Tag.name, Tag.color,
                func.count(entry_tags.c.entry_id).label("count"),
            )
            .join(entry_tags, Tag.id == entry_tags.c.tag_id)
            .group_by(Tag.id)
            .order_by(func.count(entry_tags.c.entry_id).desc())
            .limit(limit)
            .all()
        )
        return [{"name": r.name, "color": r.color, "count": r.count} for r in rows]
