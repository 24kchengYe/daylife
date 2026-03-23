"""直接对数据库所有 entry 用 LLM 分类（不走 Web 前端）"""

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env
load_dotenv(Path(__file__).parent / ".env")

from daylife.core.database import get_session
from daylife.core.models import Category, DailyEntry

CATEGORIES = ["学习", "科研", "编程", "运动", "生活", "社交", "工作", "娱乐", "休息"]

SYSTEM_PROMPT = """你是一个活动分类助手。用户会给你一批活动条目，你需要判断每条属于哪个类别。

可选类别（必须选一个，禁止回答"其他"）：
- 学习：课程、考试、复习、教材、mooc、文献阅读、ppt制作、教学、听课、培训
- 科研：论文、研究、实验、数据分析建模、算法、学术会议、项目申报、科研工具(clip/GIS/遥感/街景/城市/建筑/空间/模拟/仿真)、数据处理、投稿审稿、参考文献、访问学者交流
- 编程：写代码、软件开发、debug、网站开发、爬虫、编程环境配置、github commit、git、IDE工具、环境搭建、数据库、前后端
- 运动：跑步、健身、锻炼、体育活动、球类运动、游泳
- 生活：购物、吃饭、做饭、快递、搬家、签证、交通出行、婚礼、洗衣、打扫、修理、看病、个人事务
- 社交：聚餐、开会、组会、讨论、答辩、面试、沟通、沙龙、座谈、交流、推送(公众号)、宣传
- 工作：行政事务、值班、助教助研、材料整理、通知、奖学金、志愿服务、部门工作(体育部等)、财务、报销
- 娱乐：游戏、电影、旅游、音乐、视频观看、休闲活动、脱口秀
- 休息：睡觉、休息、午休

规则：
1. 禁止回答"其他"，必须从9个类别中选最接近的
2. [GitHub] 开头的条目一律归为"编程"
3. 科研范围很广：任何和学术研究相关的都算科研
4. 涉及ppt/推送/材料但和学术/科研相关的，归为科研而非工作

返回 JSON 数组，每个元素是类别名称。只返回 JSON。"""


def classify_batch(client, model, texts):
    user_msg = json.dumps(texts, ensure_ascii=False)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        temperature=0,
        max_tokens=4000,
    )
    text = resp.choices[0].message.content.strip()
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        cats = json.loads(text[start:end])
        cats = [c if c in CATEGORIES else "工作" for c in cats]
        while len(cats) < len(texts):
            cats.append("工作")
        return cats[:len(texts)]
    return ["工作"] * len(texts)


def main():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

    proxy = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    http_client = None
    if proxy:
        import httpx
        http_client = httpx.Client(proxy=proxy)
        print(f"[Proxy] {proxy}")

    client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
    print(f"[Model] {model}")

    session = get_session()
    cat_map = {c.name: c.id for c in session.query(Category).all()}
    print(f"[Categories] {list(cat_map.keys())}")

    # 获取未分类的
    entries = session.query(DailyEntry).filter(DailyEntry.ai_classified == 0).order_by(DailyEntry.date).all()
    total = len(entries)
    print(f"[Total] {total} entries to classify")

    batch_size = 50
    done = 0
    errors = 0

    for i in range(0, total, batch_size):
        batch = entries[i:i + batch_size]
        texts = [e.content for e in batch]

        try:
            cats = classify_batch(client, model, texts)
            for entry, cat_name in zip(batch, cats):
                if cat_name in cat_map:
                    entry.category_id = cat_map[cat_name]
                entry.ai_classified = 1
            session.commit()
            done += len(batch)
            pct = round(done / total * 100)
            print(f"  [{pct}%] {done}/{total} done")
        except Exception as e:
            errors += 1
            print(f"  [ERROR] batch {i}: {e}")
            if errors > 5:
                print("Too many errors, stopping")
                break
            time.sleep(2)
            continue

    print(f"\nDone! {done}/{total} classified, {errors} errors")
    session.close()


if __name__ == "__main__":
    main()
