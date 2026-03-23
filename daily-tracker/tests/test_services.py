"""业务服务层测试 - EntryService + StatsService

使用内存 SQLite 数据库，测试业务逻辑和统计功能。
"""

import pytest
from datetime import date, time, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from daylife.core.models import Base, Category
from daylife.core.database import DEFAULT_CATEGORIES
from daylife.core.schemas import EntryCreate, EntryUpdate, EntryQuery
from daylife.core.entry_service import EntryService
from daylife.core.stats_service import StatsService


# ── 测试 fixture ──

@pytest.fixture
def session():
    """创建内存数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    sess = sessionmaker(bind=engine)()
    for cat_data in DEFAULT_CATEGORIES:
        sess.add(Category(**cat_data))
    sess.commit()
    yield sess
    sess.close()


@pytest.fixture
def entry_svc(session):
    """EntryService 实例"""
    return EntryService(session)


@pytest.fixture
def stats_svc(session):
    """StatsService 实例"""
    return StatsService(session)


def _create_sample_entries(entry_svc: EntryService):
    """创建一批示例数据用于统计测试"""
    entries_data = [
        EntryCreate(date=date(2026, 3, 19), category="学习", content="阅读教材", status="completed", tags=["读书"], duration_minutes=120),
        EntryCreate(date=date(2026, 3, 19), category="运动", content="跑步", status="completed", tags=["跑步"], duration_minutes=60),
        EntryCreate(date=date(2026, 3, 20), category="编程", content="写API", status="completed", tags=["后端"], duration_minutes=180),
        EntryCreate(date=date(2026, 3, 20), category="科研", content="论文写作", status="in_progress", tags=["论文", "写作"], duration_minutes=240),
        EntryCreate(date=date(2026, 3, 21), category="编程", content="写单元测试", status="completed", tags=["测试", "后端"], duration_minutes=150),
        EntryCreate(date=date(2026, 3, 21), category="运动", content="游泳", status="completed", duration_minutes=90),
        EntryCreate(date=date(2026, 3, 21), category="社交", content="聚餐", status="completed", duration_minutes=120),
        EntryCreate(date=date(2026, 3, 21), category="学习", content="看视频教程", status="incomplete", tags=["视频"], duration_minutes=60),
    ]
    return entry_svc.batch_create(entries_data)


# ══════════════════════════════════════════════════════════════
# EntryService 测试
# ══════════════════════════════════════════════════════════════


class TestEntryServiceCRUD:
    """EntryService 增删改查测试"""

    def test_add_entry_basic(self, entry_svc):
        """测试基本创建记录"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21),
            category="科研",
            content="完成论文第三章",
            priority=5,
        ))
        assert entry.id is not None
        assert entry.category.name == "科研"
        assert entry.priority == 5

    def test_add_entry_with_tags(self, entry_svc):
        """测试创建带标签的记录"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21),
            content="重构代码",
            tags=["重构", "Python", "后端"],
        ))
        assert len(entry.tags) == 3
        tag_names = {t.name for t in entry.tags}
        assert "重构" in tag_names
        assert "Python" in tag_names

    def test_add_entry_auto_duration(self, entry_svc):
        """测试自动计算时长（start_time + end_time → duration_minutes）"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21),
            content="上午编程",
            start_time=time(9, 0),
            end_time=time(12, 30),
        ))
        assert entry.duration_minutes == 210  # 3.5小时 = 210分钟

    def test_add_entry_invalid_category(self, entry_svc):
        """分类不存在时，category_id 应为 None"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21),
            category="不存在的分类",
            content="测试",
        ))
        assert entry.category_id is None

    def test_get_entry(self, entry_svc):
        """测试获取单条记录"""
        created = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21), content="被查询的记录",
        ))
        fetched = entry_svc.get_entry(created.id)
        assert fetched is not None
        assert fetched.content == "被查询的记录"

    def test_get_entries_by_date(self, entry_svc):
        """测试按日期查询"""
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 21), content="A"))
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 21), content="B"))
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 22), content="C"))

        entries = entry_svc.get_entries_by_date(date(2026, 3, 21))
        assert len(entries) == 2

    def test_get_entries_by_date_range(self, entry_svc):
        """测试日期范围查询带分类过滤"""
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 20), category="编程", content="A"))
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 21), category="编程", content="B"))
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 21), category="运动", content="C"))

        entries = entry_svc.get_entries_by_date_range(
            date(2026, 3, 20), date(2026, 3, 21), category="编程",
        )
        assert len(entries) == 2

    def test_search_with_query(self, entry_svc):
        """测试综合搜索"""
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 21), content="论文写作", status="completed"))
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 21), content="论文修改", status="incomplete"))
        entry_svc.add_entry(EntryCreate(date=date(2026, 3, 21), content="跑步", status="completed"))

        results = entry_svc.search(EntryQuery(keyword="论文", status="completed"))
        assert len(results) == 1
        assert "论文写作" in results[0].content

    def test_update_entry(self, entry_svc):
        """测试更新记录"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21), content="原内容", status="in_progress",
        ))
        updated = entry_svc.update_entry(entry.id, EntryUpdate(
            content="更新内容", status="completed",
        ))
        assert updated.content == "更新内容"
        assert updated.status == "completed"

    def test_update_entry_change_category(self, entry_svc):
        """测试更新记录的分类"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21), category="学习", content="看论文",
        ))
        updated = entry_svc.update_entry(entry.id, EntryUpdate(category="科研"))
        assert updated.category.name == "科研"

    def test_update_entry_change_tags(self, entry_svc):
        """测试更新记录的标签"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21), content="写代码", tags=["A", "B"],
        ))
        updated = entry_svc.update_entry(entry.id, EntryUpdate(tags=["C", "D", "E"]))
        assert len(updated.tags) == 3
        tag_names = {t.name for t in updated.tags}
        assert tag_names == {"C", "D", "E"}

    def test_delete_entry(self, entry_svc):
        """测试删除记录"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21), content="待删除",
        ))
        assert entry_svc.delete_entry(entry.id) is True
        assert entry_svc.get_entry(entry.id) is None

    def test_delete_nonexistent(self, entry_svc):
        """删除不存在的记录应返回 False"""
        assert entry_svc.delete_entry(9999) is False

    def test_mark_completed(self, entry_svc):
        """测试标记完成"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21), content="进行中", status="in_progress",
        ))
        updated = entry_svc.mark_completed(entry.id)
        assert updated.status == "completed"

    def test_mark_incomplete(self, entry_svc):
        """测试标记未完成"""
        entry = entry_svc.add_entry(EntryCreate(
            date=date(2026, 3, 21), content="完成的", status="completed",
        ))
        updated = entry_svc.mark_incomplete(entry.id)
        assert updated.status == "incomplete"

    def test_batch_create(self, entry_svc):
        """测试批量创建"""
        data = [
            EntryCreate(date=date(2026, 3, 21), content=f"批量{i}", category="编程")
            for i in range(5)
        ]
        results = entry_svc.batch_create(data)
        assert len(results) == 5
        assert all(e.category.name == "编程" for e in results)

    def test_list_categories(self, entry_svc):
        """测试列出分类"""
        cats = entry_svc.list_categories()
        assert len(cats) == len(DEFAULT_CATEGORIES)

    def test_get_category_stats(self, entry_svc):
        """测试分类统计"""
        _create_sample_entries(entry_svc)
        stats = entry_svc.get_category_stats(date(2026, 3, 19), date(2026, 3, 21))

        # 应有多个分类
        assert len(stats) > 0
        # 编程分类应有2条
        coding_stat = next(s for s in stats if s["category"] == "编程")
        assert coding_stat["count"] == 2

    def test_calc_duration_normal(self):
        """测试时长计算 - 普通情况"""
        assert EntryService._calc_duration(time(9, 0), time(12, 30)) == 210

    def test_calc_duration_cross_midnight(self):
        """测试时长计算 - 跨午夜"""
        assert EntryService._calc_duration(time(23, 0), time(1, 0)) == 120


# ══════════════════════════════════════════════════════════════
# StatsService 测试
# ══════════════════════════════════════════════════════════════


class TestStatsOverview:
    """总览统计测试"""

    def test_overview_empty(self, stats_svc):
        """空数据库的总览统计"""
        overview = stats_svc.get_overview()
        assert overview["total_entries"] == 0
        assert overview["completion_rate"] == 0
        assert overview["total_days"] == 0

    def test_overview_with_data(self, entry_svc, stats_svc):
        """有数据时的总览统计"""
        _create_sample_entries(entry_svc)
        overview = stats_svc.get_overview()

        assert overview["total_entries"] == 8
        assert overview["completed_entries"] == 6
        assert overview["total_days"] == 3
        assert overview["completion_rate"] == 75.0

    def test_overview_with_date_filter(self, entry_svc, stats_svc):
        """带日期过滤的总览统计"""
        _create_sample_entries(entry_svc)
        overview = stats_svc.get_overview(
            date_from=date(2026, 3, 21), date_to=date(2026, 3, 21),
        )
        assert overview["total_entries"] == 4  # 3月21日有4条记录


class TestStatsSummary:
    """日/周/月/年汇总测试"""

    def test_daily_summary(self, entry_svc, stats_svc):
        """测试每日汇总"""
        _create_sample_entries(entry_svc)
        summary = stats_svc.get_daily_summary(date(2026, 3, 21))

        assert summary["total"] == 4
        assert summary["completed"] == 3
        assert summary["incomplete"] == 1
        assert summary["completion_rate"] == 75.0
        assert "编程" in summary["by_category"]

    def test_daily_summary_empty(self, stats_svc):
        """无记录日期的汇总"""
        summary = stats_svc.get_daily_summary(date(2026, 1, 1))
        assert summary["total"] == 0
        assert summary["completion_rate"] == 0

    def test_weekly_summary(self, entry_svc, stats_svc):
        """测试周汇总"""
        _create_sample_entries(entry_svc)
        # 2026-03-16 是周一（3/19-3/21 在这一周内）
        summary = stats_svc.get_weekly_summary(date(2026, 3, 16))

        assert summary["total"] == 8
        assert summary["active_days"] == 3
        assert summary["week_start"] == date(2026, 3, 16)

    def test_monthly_summary(self, entry_svc, stats_svc):
        """测试月度汇总"""
        _create_sample_entries(entry_svc)
        summary = stats_svc.get_monthly_summary(2026, 3)

        assert summary["total"] == 8
        assert summary["active_days"] == 3
        assert summary["total_days"] == 31  # 3月有31天

    def test_yearly_summary(self, entry_svc, stats_svc):
        """测试年度汇总"""
        _create_sample_entries(entry_svc)
        summary = stats_svc.get_yearly_summary(2026)

        assert summary["total"] == 8
        assert 3 in summary["monthly_counts"]
        assert summary["monthly_counts"][3] == 8


class TestStatsCompletion:
    """完成率统计测试"""

    def test_completion_by_category(self, entry_svc, stats_svc):
        """测试按分类的完成率"""
        _create_sample_entries(entry_svc)
        result = stats_svc.get_completion_rate_by_category(
            date(2026, 3, 19), date(2026, 3, 21),
        )
        assert len(result) > 0

        # 运动分类应该100%完成
        sports = next(r for r in result if r["category"] == "运动")
        assert sports["completion_rate"] == 100.0

        # 学习分类：1 completed + 1 incomplete = 50%
        study = next(r for r in result if r["category"] == "学习")
        assert study["completion_rate"] == 50.0

    def test_completion_by_week(self, entry_svc, stats_svc):
        """测试按周的完成率趋势"""
        _create_sample_entries(entry_svc)
        result = stats_svc.get_completion_rate_by_week(weeks=4)

        assert len(result) == 4
        # 最后一周（包含样本数据）应有数据
        last_week = result[-1]
        assert last_week["total"] > 0


class TestStatsDistribution:
    """分类占比测试"""

    def test_category_distribution(self, entry_svc, stats_svc):
        """测试分类占比计算"""
        _create_sample_entries(entry_svc)
        result = stats_svc.get_category_distribution(
            date(2026, 3, 19), date(2026, 3, 21),
        )
        assert len(result) > 0

        # 所有 count_ratio 之和应接近 100%
        total_ratio = sum(r["count_ratio"] for r in result)
        assert abs(total_ratio - 100.0) < 0.5


class TestStatsHeatmap:
    """热力图数据测试"""

    def test_heatmap_data(self, entry_svc, stats_svc):
        """测试热力图数据生成"""
        _create_sample_entries(entry_svc)
        result = stats_svc.get_heatmap_data(date(2026, 3, 19), date(2026, 3, 21))

        assert len(result) == 3  # 3天有数据
        # 3月21日有4条记录
        day21 = next(r for r in result if r["date"] == date(2026, 3, 21))
        assert day21["count"] == 4
        assert day21["completed"] == 3


class TestStatsTrend:
    """趋势分析测试"""

    def test_trend_by_day(self, entry_svc, stats_svc):
        """测试按天的趋势数据"""
        _create_sample_entries(entry_svc)
        result = stats_svc.get_trend_data(
            date(2026, 3, 19), date(2026, 3, 21), group_by="day",
        )
        assert len(result) == 3  # 3天

    def test_trend_by_week(self, entry_svc, stats_svc):
        """测试按周的趋势数据"""
        _create_sample_entries(entry_svc)
        result = stats_svc.get_trend_data(
            date(2026, 3, 19), date(2026, 3, 21), group_by="week",
        )
        assert len(result) >= 1

    def test_trend_by_month(self, entry_svc, stats_svc):
        """测试按月的趋势数据"""
        _create_sample_entries(entry_svc)
        result = stats_svc.get_trend_data(
            date(2026, 3, 19), date(2026, 3, 21), group_by="month",
        )
        assert len(result) == 1  # 全在3月


class TestStatsStreak:
    """连续天数统计测试"""

    def test_streak_empty(self, stats_svc):
        """空数据库无连续记录"""
        assert stats_svc.get_current_streak() == 0

    def test_streak_consecutive(self, entry_svc, stats_svc):
        """测试连续多天的 streak 计算"""
        today = date.today()
        for i in range(5):
            entry_svc.add_entry(EntryCreate(
                date=today - timedelta(days=i), content=f"第{i}天",
            ))

        assert stats_svc.get_current_streak() == 5

    def test_streak_with_gap(self, entry_svc, stats_svc):
        """测试有间断时的 streak（只计算连续部分）"""
        today = date.today()
        # 今天和昨天有记录，前天没有，大前天有
        entry_svc.add_entry(EntryCreate(date=today, content="今天"))
        entry_svc.add_entry(EntryCreate(date=today - timedelta(days=1), content="昨天"))
        entry_svc.add_entry(EntryCreate(date=today - timedelta(days=3), content="大前天"))

        assert stats_svc.get_current_streak() == 2

    def test_longest_streak(self, entry_svc, stats_svc):
        """测试历史最长连续天数"""
        base = date(2026, 1, 1)
        # 第一段：3天
        for i in range(3):
            entry_svc.add_entry(EntryCreate(date=base + timedelta(days=i), content=f"A{i}"))
        # 间隔2天
        # 第二段：5天
        for i in range(5):
            entry_svc.add_entry(EntryCreate(date=base + timedelta(days=5 + i), content=f"B{i}"))

        result = stats_svc.get_longest_streak()
        assert result["days"] == 5
        assert result["start"] == date(2026, 1, 6)
        assert result["end"] == date(2026, 1, 10)

    def test_longest_streak_empty(self, stats_svc):
        """空数据库的最长连续天数"""
        result = stats_svc.get_longest_streak()
        assert result["days"] == 0


class TestStatsTagFrequency:
    """标签频次统计测试"""

    def test_tag_frequency(self, entry_svc, stats_svc):
        """测试标签频次统计"""
        _create_sample_entries(entry_svc)
        result = stats_svc.get_tag_frequency(limit=10)

        assert len(result) > 0
        # "后端" 标签出现了2次
        backend = next(r for r in result if r["name"] == "后端")
        assert backend["count"] == 2
