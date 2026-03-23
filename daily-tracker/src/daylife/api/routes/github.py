"""GitHub commit 集成 - 拉取 commit 并导入数据库"""

import json
import subprocess
from datetime import date, timedelta

from fastapi import APIRouter, Query

from daylife.core.database import get_session
from daylife.core.models import Category, DailyEntry
from daylife.core.schemas import ApiResponse

router = APIRouter()


def _fetch_commits(user, start_str, end_str):
    """用 gh CLI 拉取 commits，按日期+仓库汇总"""
    end_plus = (date.fromisoformat(end_str) + timedelta(days=1)).isoformat()
    result = subprocess.run(
        ["gh", "search", "commits",
         f"--author={user}",
         f"--author-date={start_str}..{end_plus}",
         "--limit", "500",
         "--json", "repository,commit"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
    )
    if result.returncode != 0:
        return None, result.stderr[:200]

    commits = json.loads(result.stdout) if result.stdout.strip() else []

    # 按日期+仓库汇总
    by_date = {}
    for c in commits:
        repo_name = c.get("repository", {}).get("name", "unknown")
        commit_info = c.get("commit", {})
        msg = commit_info.get("message", "").split("\n")[0][:80]
        authored = commit_info.get("authoredDate", "") or commit_info.get("committedDate", "")
        if not authored:
            committer = commit_info.get("committer", {})
            authored = committer.get("date", "")
        commit_date = authored[:10] if authored else None
        if not commit_date:
            continue
        if commit_date not in by_date:
            by_date[commit_date] = {}
        if repo_name not in by_date[commit_date]:
            by_date[commit_date][repo_name] = []
        by_date[commit_date][repo_name].append(msg)

    return by_date, None


@router.get("/commits", response_model=ApiResponse)
def get_github_commits(
    start: date = Query(...),
    end: date = Query(...),
    user: str = Query("24kchengYe"),
):
    """获取 GitHub 每日 commit 摘要（按仓库汇总，不入库）"""
    try:
        by_date, err = _fetch_commits(user, start.isoformat(), end.isoformat())
        if err:
            return ApiResponse(code=500, message=f"gh error: {err}")

        output = {}
        for d, repos in sorted(by_date.items()):
            output[d] = []
            for repo, msgs in repos.items():
                unique = list(dict.fromkeys(msgs))
                summary = ", ".join(unique[:5])
                if len(unique) > 5:
                    summary += f" 等{len(unique)}项"
                output[d].append({"repo": repo, "count": len(unique), "summary": summary})
        return ApiResponse(data=output)
    except subprocess.TimeoutExpired:
        return ApiResponse(code=500, message="GitHub API 超时")
    except Exception as e:
        return ApiResponse(code=500, message=str(e))


@router.get("/sync", response_model=ApiResponse)
def sync_github_commits(
    start: date = Query(..., description="起始日期"),
    end: date = Query(..., description="截止日期"),
    user: str = Query("24kchengYe"),
):
    """拉取 GitHub commits 并导入数据库（按仓库汇总，每个仓库每天一条 entry）

    去重：同一天同一仓库不重复导入（通过 source='github' + content 匹配）
    """
    try:
        by_date, err = _fetch_commits(user, start.isoformat(), end.isoformat())
        if err:
            return ApiResponse(code=500, message=f"gh error: {err}")

        session = get_session()
        # 找 GitHub 分类
        gh_cat = session.query(Category).filter(Category.name == "GitHub").first()
        gh_id = gh_cat.id if gh_cat else None

        imported = 0
        skipped = 0

        for d, repos in by_date.items():
            d_date = date.fromisoformat(d)
            for repo, msgs in repos.items():
                unique = list(dict.fromkeys(msgs))
                summary = ", ".join(unique[:5])
                if len(unique) > 5:
                    summary += f" 等{len(unique)}项"
                content = f"[GitHub] {repo}: {summary}"

                # 检查是否已存在
                existing = session.query(DailyEntry).filter(
                    DailyEntry.date == d_date,
                    DailyEntry.source == "github",
                    DailyEntry.content.contains(f"[GitHub] {repo}:"),
                ).first()

                if existing:
                    skipped += 1
                    continue

                entry = DailyEntry(
                    date=d_date,
                    category_id=gh_id,
                    content=content,
                    status="completed",
                    source="github",
                    ai_classified=1,  # 直接标记为编程，不需要 AI 再分
                )
                session.add(entry)
                imported += 1

        session.commit()
        session.close()

        return ApiResponse(data={
            "imported": imported,
            "skipped": skipped,
            "total_dates": len(by_date),
        })

    except subprocess.TimeoutExpired:
        return ApiResponse(code=500, message="GitHub API 超时")
    except Exception as e:
        return ApiResponse(code=500, message=str(e))
