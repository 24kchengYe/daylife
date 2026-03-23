"""AI 报告路由 — 周报/月报/年报生成与查看 + 格式统一 + 词云"""

import re
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import func as sqlfunc

from daylife.core.database import get_session
from daylife.core.llm import get_llm_client
from daylife.core.models import Category, DailyEntry, Report
from daylife.core.schemas import ApiResponse, ReportOut

router = APIRouter()

REPORT_MODEL = "minimax/minimax-01"

# 词云缓存目录
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
WORDCLOUD_DIR = _PROJECT_ROOT / "wordclouds"
WORDCLOUD_DIR.mkdir(exist_ok=True)


# ── 工具函数 ──

def _iso_week_to_dates(week_str: str):
    """'2026-W12' -> (date_from, date_to)"""
    year, week = int(week_str[:4]), int(week_str.split("W")[1])
    # ISO week: Monday of week 1 contains Jan 4
    jan4 = date(year, 1, 4)
    start_of_w1 = jan4 - timedelta(days=jan4.isoweekday() - 1)
    monday = start_of_w1 + timedelta(weeks=week - 1)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _month_to_dates(month_str: str):
    """'2026-03' -> (date_from, date_to)"""
    year, month = int(month_str[:4]), int(month_str[5:7])
    first = date(year, month, 1)
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return first, last


def _year_to_dates(year_str: str):
    """'2026' -> (date_from, date_to)"""
    year = int(year_str)
    return date(year, 1, 1), date(year, 12, 31)


def _get_period_dates(period_type: str, period_key: str):
    if period_type == "week":
        return _iso_week_to_dates(period_key)
    elif period_type == "month":
        return _month_to_dates(period_key)
    elif period_type == "year":
        return _year_to_dates(period_key)
    raise ValueError(f"Unknown period_type: {period_type}")


def _build_prompt(period_type: str, period_key: str, entries_text: str) -> str:
    type_label = {"week": "周报", "month": "月报", "year": "年报"}[period_type]
    return f"""请为以下时间段生成一份{type_label}，用中文回答。

时间段：{period_key}
类型：{type_label}

以下是该时间段内的所有活动记录：
{entries_text}

请分析以下方面并输出 Markdown 格式的报告：
1. **总览**：总共多少条活动，涵盖多少天
2. **分类分布**：各类别（学习、科研、编程、运动等）的数量和占比
3. **重点成就**：主要完成了哪些事情（挑重点，不要罗列所有条目）
4. **模式与趋势**：活跃度变化、时间分配习惯等
5. **建议**：基于数据给出改善建议

格式要求：
- 使用 Markdown 标题（##）分隔各部分
- 简洁有力，不要啰嗦
- 每个部分 3-5 行即可"""


def _entries_to_text(entries, period_type: str) -> str:
    """将 entries 转为 LLM 可读文本"""
    if period_type == "week":
        # 按日分组
        by_date = defaultdict(list)
        for e in entries:
            cat_name = e.category.name if e.category else "未分类"
            status = "V" if e.status == "completed" else "X"
            by_date[str(e.date)].append(f"[{status}][{cat_name}] {e.content}")
        lines = []
        for d in sorted(by_date.keys()):
            lines.append(f"\n### {d}")
            for item in by_date[d]:
                lines.append(f"- {item}")
        return "\n".join(lines)

    elif period_type == "month":
        # 按周分组摘要
        by_week = defaultdict(list)
        for e in entries:
            iso = e.date.isocalendar()
            wk = f"{iso.year}-W{iso.week:02d}"
            cat_name = e.category.name if e.category else "未分类"
            by_week[wk].append(f"[{cat_name}] {e.content}")
        lines = []
        for wk in sorted(by_week.keys()):
            lines.append(f"\n### {wk} ({len(by_week[wk])} 条)")
            for item in by_week[wk][:20]:
                lines.append(f"- {item}")
            if len(by_week[wk]) > 20:
                lines.append(f"- ...还有 {len(by_week[wk]) - 20} 条")
        return "\n".join(lines)

    else:  # year
        # 按月分组摘要
        by_month = defaultdict(list)
        for e in entries:
            mk = e.date.strftime("%Y-%m")
            cat_name = e.category.name if e.category else "未分类"
            by_month[mk].append(f"[{cat_name}] {e.content}")
        lines = []
        for mk in sorted(by_month.keys()):
            lines.append(f"\n### {mk} ({len(by_month[mk])} 条)")
            for item in by_month[mk][:15]:
                lines.append(f"- {item}")
            if len(by_month[mk]) > 15:
                lines.append(f"- ...还有 {len(by_month[mk]) - 15} 条")
        return "\n".join(lines)


def _build_format_prompt(report_content: str, period_key: str) -> str:
    """构建格式化报告的 LLM prompt"""
    return f"""请将以下报告重新格式化，严格按照模板输出。保留所有事实内容不变，只调整 Markdown 格式结构。只输出格式化后的 Markdown，不要任何额外说明。

模板：
# {period_key} 报告

## 总览
- 总活动数：X 条
- 时间跨度：X 天
- 日均活动：X 条/天

## 分类分布
| 类别 | 数量 | 占比 |
|------|------|------|
| 科研 | X | X% |
...

## 重点成就
1. **XXX**：描述
2. **XXX**：描述

## 模式与趋势
- 趋势1
- 趋势2

## 建议
- 建议1
- 建议2

原始报告内容：
{report_content}"""


# ── 路由 ──

@router.get("/tree", response_model=ApiResponse)
def report_tree():
    """返回报告树：年 > 月 > 周，带 has_report 和 formatted 标志"""
    session = get_session()
    try:
        # 获取数据范围
        min_date = session.query(sqlfunc.min(DailyEntry.date)).scalar()
        max_date = session.query(sqlfunc.max(DailyEntry.date)).scalar()
        if not min_date or not max_date:
            return ApiResponse(data=[])

        # 已有报告的 period_key -> formatted 映射
        existing_reports = {
            r.period_key: r.formatted
            for r in session.query(Report.period_key, Report.formatted).all()
        }

        tree = []
        for year in range(max_date.year, min_date.year - 1, -1):
            year_key = str(year)
            year_node = {
                "key": year_key, "label": f"{year}年", "type": "year",
                "has_report": year_key in existing_reports,
                "formatted": existing_reports.get(year_key, 0),
                "children": [],
            }
            for month in range(12, 0, -1):
                month_key = f"{year}-{month:02d}"
                month_start, month_end = _month_to_dates(month_key)
                # 跳过未来和数据之前的月份
                if month_start > max_date or month_end < min_date:
                    continue
                month_node = {
                    "key": month_key, "label": f"{month}月", "type": "month",
                    "has_report": month_key in existing_reports,
                    "formatted": existing_reports.get(month_key, 0),
                    "children": [],
                }
                # 该月的所有 ISO 周
                d = month_start
                seen_weeks = set()
                while d <= month_end:
                    iso = d.isocalendar()
                    wk = f"{iso.year}-W{iso.week:02d}"
                    if wk not in seen_weeks:
                        seen_weeks.add(wk)
                        wk_start, wk_end = _iso_week_to_dates(wk)
                        month_node["children"].append({
                            "key": wk, "label": f"第{iso.week}周", "type": "week",
                            "has_report": wk in existing_reports,
                            "formatted": existing_reports.get(wk, 0),
                            "date_range": f"{wk_start} ~ {wk_end}",
                        })
                    d += timedelta(days=1)
                year_node["children"].append(month_node)
            tree.append(year_node)
        return ApiResponse(data=tree)
    finally:
        session.close()


@router.get("/generate", response_model=ApiResponse)
def generate_report(
    period_type: str = Query(..., description="week|month|year"),
    period_key: str = Query(..., description="如 2026-W12, 2026-03, 2026"),
    force: bool = Query(False, description="是否强制重新生成"),
):
    """生成单个报告（GET 避免代理问题）"""
    session = get_session()
    try:
        # 检查是否已存在
        existing = session.query(Report).filter_by(period_key=period_key).first()
        if existing and not force:
            return ApiResponse(data=ReportOut.model_validate(existing))

        # 获取日期范围
        date_from, date_to = _get_period_dates(period_type, period_key)

        # 查询 entries
        entries = (
            session.query(DailyEntry)
            .filter(DailyEntry.date >= date_from, DailyEntry.date <= date_to)
            .order_by(DailyEntry.date)
            .all()
        )
        if not entries:
            return ApiResponse(code=404, message=f"{period_key} 没有活动记录")

        # 构建 prompt 并调用 LLM
        entries_text = _entries_to_text(entries, period_type)
        prompt = _build_prompt(period_type, period_key, entries_text)

        client, model = get_llm_client(model_override=REPORT_MODEL)
        if not client:
            return ApiResponse(code=500, message="未配置 OPENAI_API_KEY")

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个数据分析助手，擅长从活动记录中提取洞察。用中文回答。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        content = resp.choices[0].message.content.strip()

        # 提取标题（第一个 # 标题）
        title_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
        title = title_match.group(1) if title_match else f"{period_key} 报告"

        # 保存到数据库（生成/重新生成时 formatted=0）
        if existing:
            existing.content = content
            existing.title = title
            existing.model_used = model
            existing.entry_count = len(entries)
            existing.formatted = 0
            existing.generated_at = datetime.now()
            report = existing
        else:
            report = Report(
                period_type=period_type,
                period_key=period_key,
                date_from=date_from,
                date_to=date_to,
                title=title,
                content=content,
                model_used=model,
                entry_count=len(entries),
                formatted=0,
            )
            session.add(report)
        session.commit()
        session.refresh(report)

        return ApiResponse(data=ReportOut.model_validate(report))
    except Exception as e:
        session.rollback()
        return ApiResponse(code=500, message=f"生成报告失败: {str(e)}")
    finally:
        session.close()


@router.get("/generate-all", response_model=ApiResponse)
def generate_all():
    """生成下一个缺失的报告（周→月→年），返回 {done, remaining}。前端轮询。"""
    session = get_session()
    try:
        min_date = session.query(sqlfunc.min(DailyEntry.date)).scalar()
        max_date = session.query(sqlfunc.max(DailyEntry.date)).scalar()
        if not min_date or not max_date:
            return ApiResponse(data={"done": True, "remaining": 0})

        existing_keys = {r.period_key for r in session.query(Report.period_key).all()}

        # 找出哪些周/月有数据
        dates_with_data = {r.date for r in session.query(DailyEntry.date).distinct().all()}
        session.close()

        missing = []

        # 周报：只生成有数据的周
        seen_weeks = set()
        for d in sorted(dates_with_data):
            if d < min_date or d > max_date:
                continue
            iso = d.isocalendar()
            wk = f"{iso.year}-W{iso.week:02d}"
            if wk not in seen_weeks:
                seen_weeks.add(wk)
                if wk not in existing_keys:
                    missing.append(("week", wk))

        # 月报：只生成有数据的月
        seen_months = set()
        for d in sorted(dates_with_data):
            mk = f"{d.year}-{d.month:02d}"
            if mk not in seen_months:
                seen_months.add(mk)
                if mk not in existing_keys:
                    missing.append(("month", mk))

        # 年报：只生成有数据的年
        seen_years = set()
        for d in sorted(dates_with_data):
            yk = str(d.year)
            if yk not in seen_years:
                seen_years.add(yk)
                if yk not in existing_keys:
                    missing.append(("year", yk))

        if not missing:
            return ApiResponse(data={"done": True, "remaining": 0})

        # 生成第一个缺失的
        period_type, period_key = missing[0]
        result = generate_report(period_type=period_type, period_key=period_key, force=False)

        return ApiResponse(data={
            "done": False,
            "remaining": len(missing) - 1,
            "generated": period_key,
        })
    except Exception as e:
        return ApiResponse(code=500, message=f"批量生成失败: {str(e)}")


# ── 格式统一 ──

@router.get("/format-one", response_model=ApiResponse)
def format_one_report(
    period_key: str = Query(..., description="要格式化的报告 period_key"),
):
    """格式化单个报告，使用 LLM 重新排版为统一模板"""
    session = get_session()
    try:
        report = session.query(Report).filter_by(period_key=period_key).first()
        if not report:
            return ApiResponse(code=404, message=f"报告 {period_key} 不存在")

        if report.formatted == 1:
            return ApiResponse(data=ReportOut.model_validate(report), message="已格式化，跳过")

        # 调用 LLM 格式化
        client, model = get_llm_client(model_override=REPORT_MODEL)
        if not client:
            return ApiResponse(code=500, message="未配置 OPENAI_API_KEY")

        prompt = _build_format_prompt(report.content, period_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个 Markdown 格式化助手。将报告重新格式化为指定模板，保留所有事实内容不变，只调整格式。只输出格式化后的 Markdown。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=4000,
        )
        formatted_content = resp.choices[0].message.content.strip()

        # 更新报告
        report.content = formatted_content
        report.formatted = 1

        # 更新标题
        title_match = re.search(r"^#\s+(.+)", formatted_content, re.MULTILINE)
        if title_match:
            report.title = title_match.group(1)

        session.commit()
        session.refresh(report)

        return ApiResponse(data=ReportOut.model_validate(report))
    except Exception as e:
        session.rollback()
        return ApiResponse(code=500, message=f"格式化失败: {str(e)}")
    finally:
        session.close()


@router.get("/format-all", response_model=ApiResponse)
def format_all_reports():
    """格式化下一个未格式化的报告，返回 {done, remaining, formatted_key}。前端轮询。"""
    session = get_session()
    try:
        # 找到下一个未格式化的报告
        unformatted = (
            session.query(Report)
            .filter(Report.formatted == 0)
            .order_by(Report.period_key)
            .first()
        )
        if not unformatted:
            return ApiResponse(data={"done": True, "remaining": 0})

        remaining_count = session.query(Report).filter(Report.formatted == 0).count()
        period_key = unformatted.period_key
        session.close()

        # 调用 format_one 来格式化
        result = format_one_report(period_key=period_key)

        return ApiResponse(data={
            "done": False,
            "remaining": remaining_count - 1,
            "formatted_key": period_key,
        })
    except Exception as e:
        return ApiResponse(code=500, message=f"批量格式化失败: {str(e)}")


# ── 词云 ──

@router.get("/wordcloud")
def generate_wordcloud(
    period_type: str = Query(..., description="week|month|year"),
    period_key: str = Query(..., description="如 2026-W12, 2026-03, 2026"),
    force: bool = Query(False, description="是否强制重新生成"),
):
    """生成词云 PNG 并返回图片"""
    import io

    # 检查缓存
    safe_key = period_key.replace("/", "_")
    cache_path = WORDCLOUD_DIR / f"{safe_key}.png"
    if cache_path.exists() and not force:
        return Response(content=cache_path.read_bytes(), media_type="image/png")

    session = get_session()
    try:
        date_from, date_to = _get_period_dates(period_type, period_key)
        entries = (
            session.query(DailyEntry)
            .filter(DailyEntry.date >= date_from, DailyEntry.date <= date_to)
            .all()
        )
        if not entries:
            return ApiResponse(code=404, message=f"{period_key} 没有活动记录")

        # 合并所有文本
        all_text = " ".join(e.content for e in entries if e.content)
        if not all_text.strip():
            return ApiResponse(code=404, message="没有可用文本")

        # jieba 分词
        import jieba
        words = jieba.cut(all_text, cut_all=False)
        # 过滤停用词、短词、编号、纯数字、英文短词
        import re as _re
        stop_words = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
            "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
            "自己", "这", "他", "她", "它", "们", "那", "些", "什么", "为", "与", "从", "但",
            "被", "把", "让", "给", "可以", "这个", "那个", "还", "又", "已经", "之", "用",
            "而", "及", "或", "如", "对", "等", "做", "进行", "完成", "开始", "继续",
            "时间", "今天", "明天", "昨天", "下午", "上午", "晚上", "相关", "部分",
            "GitHub", "github", "commit", "Initial", "update", "add", "fix", "feat",
            "chore", "docs", "merge", "README", "badge", "history", "chart", "star",
            "restore", "visitor", "counter", "switch", "remove", "Track", "new", "repo",
        }
        def _is_junk(w):
            if len(w) <= 1: return True
            if w in stop_words: return True
            if _re.match(r'^[a-zA-Z]?\d+[a-zA-Z]?$', w): return True  # p1, 1h, 2h, p22 等
            if _re.match(r'^\d+m?$', w): return True  # 40m, 30 等
            if _re.match(r'^[a-zA-Z]{1,2}$', w): return True  # ai, ps 等太短
            return False
        filtered = [w for w in words if not _is_junk(w)]
        word_text = " ".join(filtered)

        if not word_text.strip():
            return ApiResponse(code=404, message="过滤后没有可用词汇")

        # 生成词云
        from wordcloud import WordCloud
        import numpy as np

        def geek_color_func(word, font_size, position, orientation, random_state=None, **kwargs):
            """赛博朋克/极客配色：青色、绿色、紫色"""
            colors = [
                "rgb(0, 255, 204)",    # 青色
                "rgb(0, 204, 255)",    # 亮蓝
                "rgb(102, 255, 178)",  # 浅绿
                "rgb(153, 102, 255)", # 紫色
                "rgb(0, 255, 136)",    # 绿色
                "rgb(77, 208, 225)",   # 青蓝
                "rgb(179, 136, 255)", # 浅紫
            ]
            import random
            rng = random if random_state is None else random_state
            if hasattr(rng, 'choice'):
                return rng.choice(colors)
            return random.choice(colors)

        # 尝试使用系统中文字体
        font_path = None
        for fp in [
            "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
            "C:/Windows/Fonts/simhei.ttf",     # 黑体
            "C:/Windows/Fonts/simsun.ttc",     # 宋体
        ]:
            if Path(fp).exists():
                font_path = fp
                break

        wc = WordCloud(
            width=900,
            height=450,
            background_color="#0d1117",
            font_path=font_path,
            max_words=80,
            max_font_size=100,
            min_font_size=16,
            color_func=geek_color_func,
            prefer_horizontal=0.85,
            margin=6,
            mode="RGBA",
        )
        wc.generate(word_text)

        # 保存到缓存
        buf = io.BytesIO()
        wc.to_image().save(buf, format="PNG")
        png_bytes = buf.getvalue()
        cache_path.write_bytes(png_bytes)

        return Response(content=png_bytes, media_type="image/png")
    except ImportError as e:
        return ApiResponse(code=500, message=f"缺少依赖: {str(e)}，请安装 wordcloud 和 jieba")
    except Exception as e:
        return ApiResponse(code=500, message=f"生成词云失败: {str(e)}")
    finally:
        session.close()


@router.get("/{period_key}", response_model=ApiResponse)
def get_report(period_key: str):
    """获取特定报告"""
    session = get_session()
    try:
        report = session.query(Report).filter_by(period_key=period_key).first()
        if not report:
            return ApiResponse(code=404, message=f"报告 {period_key} 不存在")
        return ApiResponse(data=ReportOut.model_validate(report))
    finally:
        session.close()
