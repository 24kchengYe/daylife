"""标签管理路由 — CRUD + AI 批量打标 + 进度总结"""

import json

from fastapi import APIRouter, Query
from sqlalchemy import func as sqlfunc

from daylife.core.database import get_session
from daylife.core.llm import get_llm_client
from daylife.core.models import DailyEntry, Tag, entry_tags
from daylife.core.schemas import ApiResponse, EntryOut, TagCreate, TagDetailOut

router = APIRouter()

TAG_MODEL = "minimax/minimax-01"


@router.get("", response_model=ApiResponse)
def list_tags():
    """列出所有标签及其条目数 — 单次 LEFT JOIN 查询"""
    session = get_session()
    try:
        rows = (
            session.query(
                Tag,
                sqlfunc.count(entry_tags.c.entry_id).label("cnt"),
            )
            .outerjoin(entry_tags, Tag.id == entry_tags.c.tag_id)
            .group_by(Tag.id)
            .all()
        )
        result = [
            TagDetailOut(
                id=t.id, name=t.name, color=t.color,
                description=t.description, entry_count=cnt,
            )
            for t, cnt in rows
        ]
        return ApiResponse(data=[r.model_dump() for r in result])
    finally:
        session.close()


@router.post("", response_model=ApiResponse)
def create_tag(data: TagCreate):
    """创建标签"""
    session = get_session()
    try:
        existing = session.query(Tag).filter_by(name=data.name).first()
        if existing:
            return ApiResponse(code=400, message=f"标签 '{data.name}' 已存在")
        tag = Tag(name=data.name, color=data.color, description=data.description)
        session.add(tag)
        session.commit()
        session.refresh(tag)
        return ApiResponse(data=TagDetailOut(
            id=tag.id, name=tag.name, color=tag.color,
            description=tag.description, entry_count=0,
        ).model_dump())
    except Exception as e:
        session.rollback()
        return ApiResponse(code=500, message=str(e))
    finally:
        session.close()


@router.delete("/{tag_id}", response_model=ApiResponse)
def delete_tag(tag_id: int):
    """删除标签"""
    session = get_session()
    try:
        tag = session.query(Tag).get(tag_id)
        if not tag:
            return ApiResponse(code=404, message="标签不存在")
        session.delete(tag)
        session.commit()
        return ApiResponse(data={"deleted": tag_id})
    except Exception as e:
        session.rollback()
        return ApiResponse(code=500, message=str(e))
    finally:
        session.close()


@router.get("/{tag_id}/entries", response_model=ApiResponse)
def tag_entries(tag_id: int, page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=100000)):
    """获取某标签下的所有条目"""
    session = get_session()
    try:
        tag = session.query(Tag).get(tag_id)
        if not tag:
            return ApiResponse(code=404, message="标签不存在")

        query = (
            session.query(DailyEntry)
            .join(entry_tags, DailyEntry.id == entry_tags.c.entry_id)
            .filter(entry_tags.c.tag_id == tag_id)
            .order_by(DailyEntry.date.desc())
        )
        total = query.count()
        entries = query.offset((page - 1) * limit).limit(limit).all()
        items = [EntryOut.model_validate(e) for e in entries]
        return ApiResponse(data={"items": [i.model_dump() for i in items], "total": total})
    finally:
        session.close()


@router.get("/{tag_id}/ai-batch", response_model=ApiResponse)
def ai_batch_tag(
    tag_id: int,
    batch_size: int = Query(50, ge=10, le=200),
    mode: str = Query("keyword", description="keyword=关键词匹配, ai=AI判断"),
):
    session = get_session()
    try:
        tag = session.query(Tag).get(tag_id)
        if not tag:
            return ApiResponse(code=404, message="标签不存在")

        # 获取尚未被该标签扫描过的条目（不管是否打上）
        from daylife.core.models import tag_scanned
        already_scanned = (
            session.query(tag_scanned.c.entry_id)
            .filter(tag_scanned.c.tag_id == tag_id)
            .subquery()
        )
        entries = (
            session.query(DailyEntry)
            .filter(~DailyEntry.id.in_(session.query(already_scanned.c.entry_id)))
            .order_by(DailyEntry.date)
            .limit(batch_size)
            .all()
        )

        if not entries:
            return ApiResponse(data={"tagged": 0, "total_scanned": 0, "done": True})

        matched_indices = []

        if mode == "keyword":
            # 关键词匹配模式：用标签名和描述里的关键词直接搜索
            keywords = [tag.name.lower()]
            if tag.description:
                # 描述里用逗号/顿号/空格分隔的都当关键词
                import re
                extra = re.split(r'[,，、\s]+', tag.description.lower())
                keywords.extend([k.strip() for k in extra if k.strip() and len(k.strip()) >= 2])

            for i, e in enumerate(entries):
                content_lower = e.content.lower()
                if any(kw in content_lower for kw in keywords):
                    matched_indices.append(i)

        else:
            # AI 判断模式
            tag_desc = f"标签名: {tag.name}"
            if tag.description:
                tag_desc += f"\n标签描述: {tag.description}"

            items_text = "\n".join(
                f"{i}. [{e.date}] {e.content}" for i, e in enumerate(entries)
            )

            prompt = f"""判断以下活动记录中，哪些**内容本身直接涉及**该标签主题。

{tag_desc}

严格规则：
1. 只看每条记录的**文字内容本身**，必须直接提到或明确涉及标签主题
2. 同一天的不同记录逐条独立判断
3. 宁可漏标不要误标

活动列表：
{items_text}

返回JSON数组，包含相关条目的序号（从0开始）。无相关则返回[]。只返回JSON。"""

            client, model = get_llm_client(model_override=TAG_MODEL)
            if not client:
                return ApiResponse(code=500, message="未配置 OPENAI_API_KEY")

            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一个标签分类助手。严格判断每条记录内容是否直接涉及标签主题。只返回JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=2000,
            )
            text = resp.choices[0].message.content.strip()
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                try:
                    matched_indices = json.loads(text[start:end])
                    matched_indices = [int(x) for x in matched_indices if isinstance(x, (int, float)) and 0 <= int(x) < len(entries)]
                except (json.JSONDecodeError, ValueError):
                    matched_indices = []

        # 打标 + 记录已扫描
        tagged_count = 0
        for idx in matched_indices:
            entry = entries[idx]
            if tag not in entry.tags:
                entry.tags.append(tag)
                tagged_count += 1

        # 记录所有扫描过的 entry（无论是否打上标签）
        for entry in entries:
            session.execute(
                tag_scanned.insert().prefix_with("OR IGNORE").values(
                    entry_id=entry.id, tag_id=tag_id
                )
            )
        session.commit()

        # 检查是否还有未扫描的
        remaining = (
            session.query(sqlfunc.count(DailyEntry.id))
            .filter(~DailyEntry.id.in_(session.query(already_scanned.c.entry_id)))
            .scalar() or 0
        )
        # 减去本次扫描过的
        remaining = max(0, remaining - len(entries))

        return ApiResponse(data={
            "tagged": tagged_count,
            "total_scanned": len(entries),
            "remaining": remaining,
            "done": remaining == 0,
        })

    except Exception as e:
        session.rollback()
        return ApiResponse(code=500, message=f"AI 批量打标失败: {str(e)}")
    finally:
        session.close()


@router.get("/{tag_id}/progress", response_model=ApiResponse)
def tag_progress(tag_id: int):
    """AI 生成标签的进度总结"""
    session = get_session()
    try:
        tag = session.query(Tag).get(tag_id)
        if not tag:
            return ApiResponse(code=404, message="标签不存在")

        entries = (
            session.query(DailyEntry)
            .join(entry_tags, DailyEntry.id == entry_tags.c.entry_id)
            .filter(entry_tags.c.tag_id == tag_id)
            .order_by(DailyEntry.date)
            .all()
        )

        if not entries:
            return ApiResponse(data={"summary": "该标签下没有条目", "entry_count": 0})

        # 按月汇总（避免 token 爆炸）
        from collections import defaultdict
        monthly = defaultdict(list)
        for e in entries:
            mk = f"{e.date.year}-{e.date.month:02d}"
            monthly[mk].append(e.content)

        items_text = ""
        for mk in sorted(monthly.keys()):
            items = monthly[mk]
            y, m = mk.split('-')
            items_text += f"\n### {y}年{int(m)}月 ({len(items)}条)\n"
            # 每月最多列 10 条，多的概括
            for item in items[:10]:
                items_text += f"- {item[:60]}\n"
            if len(items) > 10:
                items_text += f"- ...还有 {len(items) - 10} 条\n"

        total_count = len(entries)
        date_range = f"{entries[0].date} ~ {entries[-1].date}"

        prompt = f"""以下是与标签「{tag.name}」相关的活动记录（按月汇总），共 {total_count} 条，时间跨度 {date_range}。

{items_text}

请用中文输出 Markdown 格式的进度总结：
1. **总览**：总条数、时间跨度、涉及多少个月
2. **进度脉络**：按时间线梳理关键节点和阶段变化
3. **活跃趋势**：哪些月份最活跃，频率如何变化
4. **建议**：接下来应该关注什么

简洁有力，每部分 3-5 行。"""

        client, model = get_llm_client(model_override=TAG_MODEL)
        if not client:
            return ApiResponse(code=500, message="未配置 OPENAI_API_KEY")

        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个数据分析助手，擅长从时序活动记录中提取进度和趋势。用中文回答。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        summary = resp.choices[0].message.content.strip()
        return ApiResponse(data={"summary": summary, "entry_count": len(entries)})

    except Exception as e:
        return ApiResponse(code=500, message=f"生成进度总结失败: {str(e)}")
    finally:
        session.close()
