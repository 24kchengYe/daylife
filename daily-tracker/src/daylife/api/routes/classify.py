"""AI 分类路由 - 用 LLM 自动识别活动类别并写回数据库"""

import json

from fastapi import APIRouter, Query
from pydantic import BaseModel

from daylife.core.database import get_session
from daylife.core.llm import get_llm_client
from daylife.core.models import Category, DailyEntry
from daylife.core.schemas import ApiResponse

router = APIRouter()

CATEGORIES = ["学习", "科研", "编程", "运动", "生活", "社交", "工作", "娱乐", "休息"]

SYSTEM_PROMPT = """你是一个活动分类助手。用户会给你一批活动条目，你需要判断每条属于哪个类别。

可选类别（必须选一个，不能回答"其他"）：
- 学习：课程、考试、复习、教材、mooc、文献阅读、ppt制作、教学、听课、培训
- 科研：论文、研究、实验、数据分析建模、算法、学术会议、项目申报、科研工具(clip/GIS/遥感/街景/城市/建筑/空间/模拟/仿真)、数据处理、代码调试(科研相关)、投稿审稿、参考文献
- 编程：写代码、软件开发、debug、网站开发、爬虫、编程环境配置、github、git、IDE工具、环境搭建、数据库、前后端
- 运动：跑步、健身、锻炼、体育活动、球类运动、游泳
- 生活：购物、吃饭、做饭、快递、搬家、签证、交通出行、婚礼、洗衣、打扫、修理、看病、个人事务
- 社交：聚餐、开会、组会、讨论、答辩、面试、沟通、沙龙、座谈、交流、推送(公众号)、宣传
- 工作：行政事务、值班、助教助研、材料整理、通知、奖学金、志愿服务、部门工作(体育部等)、财务、报销
- 娱乐：游戏、电影、旅游、音乐、视频观看、休闲活动
- 休息：睡觉、休息、午休

重要规则：
1. 禁止回答"其他"，必须从以上9个类别中选最接近的一个
2. 如果活动涉及多个类别，选最主要的那个
3. 科研类的范围很广：任何和学术研究相关的活动都算科研
4. 涉及ppt、推送、材料但和学术/科研相关的，归为科研而非工作

请返回 JSON 数组，每个元素是类别名称，顺序与输入一致。只返回 JSON，不要其他文字。"""


def _get_llm_client():
    """创建 OpenAI 客户端（使用共享 LLM 工具）"""
    return get_llm_client()


def _llm_classify_batch(client, model, texts: list[str]) -> list[str]:
    """调 LLM 分类一批文本"""
    user_msg = json.dumps(texts, ensure_ascii=False)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        max_tokens=2000,
    )
    text = resp.choices[0].message.content.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        cats = json.loads(text[start:end])
        cats = [c if c in CATEGORIES else "工作" for c in cats]  # fallback 到工作而非其他
        while len(cats) < len(texts):
            cats.append("工作")
        return cats[:len(texts)]
    return ["工作"] * len(texts)


class ClassifyRequest(BaseModel):
    items: list[str]


@router.post("/batch", response_model=ApiResponse)
async def classify_batch(data: ClassifyRequest):
    """批量分类（纯文本，不写数据库）"""
    if not data.items:
        return ApiResponse(data=[])

    client, model = _get_llm_client()
    if not client:
        return ApiResponse(code=500, message="未配置 OPENAI_API_KEY")

    try:
        results = []
        for i in range(0, len(data.items), 50):
            batch = data.items[i:i + 50]
            results.extend(_llm_classify_batch(client, model, batch))
        return ApiResponse(data=results)
    except Exception as e:
        return ApiResponse(code=500, message=f"分类失败: {str(e)}")


@router.get("/status", response_model=ApiResponse)
def classify_status():
    """获取分类状态：总条目数、已分类数、未分类数"""
    session = get_session()
    try:
        total = session.query(DailyEntry).count()
        classified = session.query(DailyEntry).filter(DailyEntry.ai_classified == 1).count()
        return ApiResponse(data={
            "total": total,
            "classified": classified,
            "unclassified": total - classified,
        })
    finally:
        session.close()


@router.get("/run", response_model=ApiResponse)
async def classify_run(
    batch_size: int = Query(30, description="每批大小"),
):
    """对所有未分类的 entry 执行 AI 分类并写回数据库。
    一次调用处理一批，前端轮询调用。
    返回 {"done": N, "remaining": M}
    """
    client, model = _get_llm_client()
    if not client:
        return ApiResponse(code=500, message="未配置 OPENAI_API_KEY")

    session = get_session()
    try:
        # 获取未 AI 分类的条目（迁移后每条 entry = 一个活动）
        entries = (
            session.query(DailyEntry)
            .filter(DailyEntry.ai_classified == 0)
            .order_by(DailyEntry.date)
            .limit(batch_size)
            .all()
        )

        if not entries:
            remaining = session.query(DailyEntry).filter(DailyEntry.ai_classified == 0).count()
            return ApiResponse(data={"done": 0, "remaining": remaining})

        # 每条 entry 就是一个活动，直接分类
        texts = [e.content for e in entries]
        cats = _llm_classify_batch(client, model, texts)

        # 分类名 → ID 映射
        cat_map = {c.name: c.id for c in session.query(Category).all()}

        for entry, cat_name in zip(entries, cats):
            if cat_name in cat_map:
                entry.category_id = cat_map[cat_name]
            entry.ai_classified = 1
        session.commit()

        remaining = session.query(DailyEntry).filter(DailyEntry.ai_classified == 0).count()
        return ApiResponse(data={"done": len(entries), "remaining": remaining})

    except Exception as e:
        session.rollback()
        return ApiResponse(code=500, message=f"分类失败: {str(e)}")
    finally:
        session.close()
