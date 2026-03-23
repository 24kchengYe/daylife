"""DayLife MCP Server - 供 Claude Code / Claude Desktop 调用的每日活动记录接口

基于 mcp 库实现，提供 tools 和 resources 两类接口。
通过自然语言即可记录、查询、统计每日活动。
"""

import json
import logging
from datetime import date, datetime, time, timedelta

from mcp.server.fastmcp import FastMCP

from daylife.core.database import init_db
from daylife.core.entry_service import EntryService
from daylife.core.schemas import EntryCreate, EntryUpdate
from daylife.core.stats_service import StatsService
from daylife.core import crud

logger = logging.getLogger("daylife.mcp")

# ── 创建 MCP 服务器实例 ──
mcp = FastMCP(
    "DayLife",
    instructions="每日活动记录与统计系统。记录你每天做了什么，查询历史活动，获取统计分析。",
)


# ── 数据库会话管理 ──

def _get_services():
    """获取数据库会话和服务实例"""
    session = init_db()
    entry_svc = EntryService(session)
    stats_svc = StatsService(session)
    return session, entry_svc, stats_svc


def _entry_to_dict(entry) -> dict:
    """将 DailyEntry ORM 对象转为可序列化的字典"""
    return {
        "id": entry.id,
        "date": entry.date.isoformat(),
        "category": entry.category.name if entry.category else None,
        "category_icon": entry.category.icon if entry.category else None,
        "content": entry.content,
        "status": entry.status,
        "start_time": entry.start_time.strftime("%H:%M") if entry.start_time else None,
        "end_time": entry.end_time.strftime("%H:%M") if entry.end_time else None,
        "duration_minutes": entry.duration_minutes,
        "priority": entry.priority,
        "tags": [t.name for t in entry.tags] if entry.tags else [],
        "notes": entry.notes,
        "source": entry.source,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


def _parse_date(date_str: str | None, default: date | None = None) -> date | None:
    """解析日期字符串，支持多种格式"""
    if date_str is None:
        return default
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        pass
    # 尝试更多格式
    for fmt in ("%Y/%m/%d", "%m-%d", "%m/%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            if fmt in ("%m-%d", "%m/%d"):
                dt = dt.replace(year=date.today().year)
            return dt.date()
        except ValueError:
            continue
    return default


def _parse_time(time_str: str | None) -> time | None:
    """解析时间字符串"""
    if not time_str:
        return None
    try:
        return time.fromisoformat(time_str)
    except ValueError:
        pass
    for fmt in ("%H:%M", "%H:%M:%S", "%H%M"):
        try:
            return datetime.strptime(time_str, fmt).time()
        except ValueError:
            continue
    return None


# ══════════════════════════════════════════════════════════════
# Tools
# ══════════════════════════════════════════════════════════════


@mcp.tool()
def log_activity(
    content: str,
    category: str | None = None,
    date: str | None = None,
    time_slot: str | None = None,
    tags: str | None = None,
    status: str = "completed",
    notes: str | None = None,
    priority: int = 3,
) -> str:
    """记录一条每日活动。用于记录用户今天或某天做了什么事情。

    Args:
        content: 活动内容描述，例如"写了MCP Server的代码"、"跑步5公里"
        category: 活动分类，可选值：学习、科研、编程、运动、生活、社交、工作、娱乐、休息、其他。不填则不分类
        date: 日期，格式 YYYY-MM-DD，默认今天。支持 YYYY/MM/DD、MM-DD 等格式
        time_slot: 时间段，格式 "HH:MM-HH:MM"，例如 "09:00-11:30"。也可以只填开始时间 "09:00"
        tags: 标签，多个标签用逗号分隔，例如 "Python,MCP,开发"
        status: 状态，可选值：completed（已完成，默认）、incomplete（未完成）、in_progress（进行中）
        notes: 备注信息
        priority: 优先级 1-5，默认3。1最低5最高

    Returns:
        记录结果，包含新创建的活动ID和详情
    """
    session, entry_svc, _ = _get_services()
    try:
        # 解析日期
        entry_date = _parse_date(date, default=datetime.now().date())

        # 解析时间段
        start_time = None
        end_time = None
        if time_slot:
            parts = time_slot.split("-")
            start_time = _parse_time(parts[0].strip())
            if len(parts) > 1:
                end_time = _parse_time(parts[1].strip())

        # 解析标签
        tag_list = []
        if tags:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]

        # 创建记录
        data = EntryCreate(
            date=entry_date,
            category=category,
            content=content,
            status=status,
            start_time=start_time,
            end_time=end_time,
            priority=max(1, min(5, priority)),
            tags=tag_list,
            notes=notes,
            source="mcp",
        )
        entry = entry_svc.add_entry(data)
        result = _entry_to_dict(entry)
        return json.dumps({"success": True, "message": f"已记录活动 (ID: {entry.id})", "entry": result}, ensure_ascii=False)
    except Exception as e:
        logger.exception("log_activity failed")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def query_day(date: str | None = None) -> str:
    """查询某一天的所有活动记录。适合查看"今天做了什么"或"某天做了什么"。

    Args:
        date: 要查询的日期，格式 YYYY-MM-DD，默认今天

    Returns:
        该日期的所有活动列表，包含分类、内容、状态、时间等详情
    """
    session, entry_svc, _ = _get_services()
    try:
        target = _parse_date(date, default=datetime.now().date())
        entries = entry_svc.get_entries_by_date(target)
        result = [_entry_to_dict(e) for e in entries]
        return json.dumps({
            "date": target.isoformat(),
            "count": len(result),
            "entries": result,
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("query_day failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def query_range(
    start_date: str,
    end_date: str,
    category: str | None = None,
) -> str:
    """查询一段日期范围内的活动记录。适合查看"这周做了什么"、"上个月的运动记录"等。

    Args:
        start_date: 起始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
        category: 可选，按分类过滤。可选值：学习、科研、编程、运动、生活、社交、工作、娱乐、休息、其他

    Returns:
        日期范围内的活动列表
    """
    session, entry_svc, _ = _get_services()
    try:
        d_from = _parse_date(start_date)
        d_to = _parse_date(end_date)
        if not d_from or not d_to:
            return json.dumps({"error": "日期格式无效，请使用 YYYY-MM-DD"}, ensure_ascii=False)

        entries = entry_svc.get_entries_by_date_range(d_from, d_to, category=category)
        result = [_entry_to_dict(e) for e in entries]
        return json.dumps({
            "start_date": d_from.isoformat(),
            "end_date": d_to.isoformat(),
            "category": category,
            "count": len(result),
            "entries": result,
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("query_range failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def get_stats(
    period: str = "week",
    date: str | None = None,
) -> str:
    """获取活动统计信息。适合了解"这周的统计"、"本月完成率"、"今年做了多少事"等。

    Args:
        period: 统计周期，可选值：day（某一天）、week（某一周）、month（某一月）、year（某一年）
        date: 参考日期，格式 YYYY-MM-DD，默认今天。用于确定统计的具体周期

    Returns:
        统计信息，包含总记录数、完成率、活跃天数、分类分布等
    """
    session, _, stats_svc = _get_services()
    try:
        ref = _parse_date(date, default=datetime.now().date())

        if period == "day":
            result = stats_svc.get_daily_summary(ref)
            # 序列化 date 对象
            result["date"] = result["date"].isoformat()
        elif period == "week":
            week_start = ref - timedelta(days=ref.weekday())
            result = stats_svc.get_weekly_summary(week_start)
            result["week_start"] = result["week_start"].isoformat()
            result["week_end"] = result["week_end"].isoformat()
        elif period == "month":
            result = stats_svc.get_monthly_summary(ref.year, ref.month)
        elif period == "year":
            result = stats_svc.get_yearly_summary(ref.year)
        else:
            return json.dumps({"error": f"不支持的统计周期: {period}，请使用 day/week/month/year"}, ensure_ascii=False)

        return json.dumps({"period": period, "stats": result}, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_stats failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def search_entries(
    keyword: str,
    limit: int = 20,
) -> str:
    """全文搜索历史活动记录。适合查找"之前做过的某件事"、"关于某个关键词的活动"。

    Args:
        keyword: 搜索关键词，会匹配活动内容
        limit: 最多返回条数，默认20

    Returns:
        匹配的活动列表
    """
    session, _, _ = _get_services()
    try:
        entries = crud.search_entries(
            session,
            keyword=keyword,
            page=1,
            page_size=limit,
        )
        result = [_entry_to_dict(e) for e in entries]
        return json.dumps({
            "keyword": keyword,
            "count": len(result),
            "entries": result,
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("search_entries failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def update_entry(
    entry_id: int,
    content: str | None = None,
    category: str | None = None,
    status: str | None = None,
    tags: str | None = None,
    notes: str | None = None,
    priority: int | None = None,
    time_slot: str | None = None,
) -> str:
    """修改一条已有的活动记录。可以更新内容、分类、状态、标签等任意字段。

    Args:
        entry_id: 要修改的活动记录ID（通过查询获取）
        content: 新的活动内容描述
        category: 新的分类
        status: 新的状态：completed/incomplete/in_progress
        tags: 新的标签（逗号分隔），会替换原有标签
        notes: 新的备注
        priority: 新的优先级 1-5
        time_slot: 新的时间段，格式 "HH:MM-HH:MM"

    Returns:
        更新后的活动详情
    """
    session, entry_svc, _ = _get_services()
    try:
        # 构建更新数据
        update_fields = {}
        if content is not None:
            update_fields["content"] = content
        if category is not None:
            update_fields["category"] = category
        if status is not None:
            update_fields["status"] = status
        if notes is not None:
            update_fields["notes"] = notes
        if priority is not None:
            update_fields["priority"] = max(1, min(5, priority))
        if tags is not None:
            update_fields["tags"] = [t.strip() for t in tags.split(",") if t.strip()]

        # 解析时间段
        if time_slot is not None:
            parts = time_slot.split("-")
            st = _parse_time(parts[0].strip())
            if st:
                update_fields["start_time"] = st
            if len(parts) > 1:
                et = _parse_time(parts[1].strip())
                if et:
                    update_fields["end_time"] = et

        if not update_fields:
            return json.dumps({"success": False, "error": "没有提供要更新的字段"}, ensure_ascii=False)

        data = EntryUpdate(**update_fields)
        entry = entry_svc.update_entry(entry_id, data)
        if not entry:
            return json.dumps({"success": False, "error": f"未找到 ID={entry_id} 的记录"}, ensure_ascii=False)

        return json.dumps({
            "success": True,
            "message": f"已更新活动 (ID: {entry_id})",
            "entry": _entry_to_dict(entry),
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("update_entry failed")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def delete_entry(entry_id: int) -> str:
    """删除一条活动记录。删除后不可恢复，请谨慎操作。

    Args:
        entry_id: 要删除的活动记录ID

    Returns:
        删除结果
    """
    session, entry_svc, _ = _get_services()
    try:
        success = entry_svc.delete_entry(entry_id)
        if success:
            return json.dumps({"success": True, "message": f"已删除活动 (ID: {entry_id})"}, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": f"未找到 ID={entry_id} 的记录"}, ensure_ascii=False)
    except Exception as e:
        logger.exception("delete_entry failed")
        return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def get_categories() -> str:
    """获取所有可用的活动分类列表。每个分类有名称、图标和颜色。

    Returns:
        分类列表，包含名称、图标emoji、颜色代码
    """
    session, entry_svc, _ = _get_services()
    try:
        categories = entry_svc.list_categories()
        result = [
            {
                "id": c.id,
                "name": c.name,
                "icon": c.icon,
                "color": c.color,
            }
            for c in categories
        ]
        return json.dumps({"categories": result}, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_categories failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def get_streak() -> str:
    """获取连续记录天数（打卡streak）。查看当前连续多少天有活动记录，以及历史最长连续天数。

    Returns:
        当前连续天数和历史最长连续天数
    """
    session, _, stats_svc = _get_services()
    try:
        current = stats_svc.get_current_streak()
        longest = stats_svc.get_longest_streak()
        # 序列化日期
        if longest.get("start"):
            longest["start"] = longest["start"].isoformat()
        if longest.get("end"):
            longest["end"] = longest["end"].isoformat()

        return json.dumps({
            "current_streak": current,
            "longest_streak": longest,
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_streak failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


@mcp.tool()
def get_summary(
    start_date: str | None = None,
    end_date: str | None = None,
    period: str = "week",
) -> str:
    """生成一段时间的活动自然语言总结。适合让AI总结"这周干了什么"、"本月工作回顾"。

    Args:
        start_date: 起始日期，格式 YYYY-MM-DD。不填则根据 period 自动推算
        end_date: 结束日期，格式 YYYY-MM-DD。不填则默认今天
        period: 总结周期，可选值：week（本周）、month（本月）、year（今年）。仅在不指定日期时生效

    Returns:
        包含统计数据和分类明细的结构化信息，供AI生成自然语言总结
    """
    session, entry_svc, stats_svc = _get_services()
    try:
        today = datetime.now().date()
        d_to = _parse_date(end_date, default=today)

        if start_date:
            d_from = _parse_date(start_date, default=today)
        else:
            if period == "week":
                d_from = today - timedelta(days=today.weekday())
            elif period == "month":
                d_from = today.replace(day=1)
            elif period == "year":
                d_from = today.replace(month=1, day=1)
            else:
                d_from = today - timedelta(days=7)

        # 获取总览统计
        overview = stats_svc.get_overview(d_from, d_to)

        # 获取分类分布
        distribution = stats_svc.get_category_distribution(d_from, d_to)

        # 获取所有记录
        entries = entry_svc.get_entries_by_date_range(d_from, d_to)
        entries_data = [_entry_to_dict(e) for e in entries]

        # 按日期分组
        by_date = {}
        for e in entries_data:
            d = e["date"]
            if d not in by_date:
                by_date[d] = []
            by_date[d].append(e)

        return json.dumps({
            "period": period,
            "start_date": d_from.isoformat(),
            "end_date": d_to.isoformat(),
            "overview": overview,
            "category_distribution": distribution,
            "total_entries": len(entries_data),
            "active_dates": list(by_date.keys()),
            "entries_by_date": by_date,
        }, ensure_ascii=False)
    except Exception as e:
        logger.exception("get_summary failed")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
    finally:
        session.close()


# ══════════════════════════════════════════════════════════════
# Resources
# ══════════════════════════════════════════════════════════════


@mcp.resource("daily://today")
def resource_today() -> str:
    """今天的活动列表"""
    return query_day()


@mcp.resource("daily://stats/week")
def resource_stats_week() -> str:
    """本周活动统计"""
    return get_stats(period="week")


@mcp.resource("daily://stats/month")
def resource_stats_month() -> str:
    """本月活动统计"""
    return get_stats(period="month")


# ══════════════════════════════════════════════════════════════
# 启动入口
# ══════════════════════════════════════════════════════════════


def main():
    """启动 MCP Server（stdio 传输模式）"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
    logger.info("DayLife MCP Server starting...")
    mcp.run()


if __name__ == "__main__":
    main()
