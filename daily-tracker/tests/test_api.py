"""API 路由测试"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event

from daylife.core.models import Base, Category
from daylife.core.database import DEFAULT_CATEGORIES


@pytest.fixture()
def client(tmp_path):
    """创建使用临时数据库的测试客户端"""
    db_path = tmp_path / "test.db"
    os.environ["DAYLIFE_DB_PATH"] = str(db_path)

    # 强制重新导入以使用新的环境变量
    from daylife.api.main import create_app
    app = create_app()
    with TestClient(app) as c:
        yield c

    os.environ.pop("DAYLIFE_DB_PATH", None)


# ══════════════════════════════════════════════════════════════
# Health
# ══════════════════════════════════════════════════════════════


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


# ══════════════════════════════════════════════════════════════
# Entries CRUD
# ══════════════════════════════════════════════════════════════


class TestEntries:
    def _create_entry(self, client, **overrides):
        payload = {
            "date": "2026-03-21",
            "content": "写代码",
            "category": "编程",
            "status": "completed",
            "source": "web",
        }
        payload.update(overrides)
        return client.post("/api/entries", json=payload)

    def test_create_entry(self, client):
        r = self._create_entry(client)
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["content"] == "写代码"
        assert body["data"]["id"] >= 1

    def test_list_entries(self, client):
        self._create_entry(client, content="任务A")
        self._create_entry(client, content="任务B")
        r = client.get("/api/entries")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["total"] >= 2

    def test_list_entries_by_date(self, client):
        self._create_entry(client, date="2026-01-15", content="一月任务")
        self._create_entry(client, date="2026-03-21", content="三月任务")
        r = client.get("/api/entries", params={"date": "2026-01-15"})
        body = r.json()
        assert body["code"] == 0
        assert len(body["data"]["items"]) >= 1
        assert all(e["date"] == "2026-01-15" for e in body["data"]["items"])

    def test_list_entries_pagination(self, client):
        for i in range(5):
            self._create_entry(client, content=f"任务{i}")
        r = client.get("/api/entries", params={"page": 1, "limit": 2})
        body = r.json()
        assert len(body["data"]["items"]) == 2
        assert body["data"]["total"] >= 5

    def test_update_entry(self, client):
        r = self._create_entry(client)
        entry_id = r.json()["data"]["id"]
        r = client.put(f"/api/entries/{entry_id}", json={"content": "改了内容"})
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["content"] == "改了内容"

    def test_update_nonexistent(self, client):
        r = client.put("/api/entries/99999", json={"content": "xxx"})
        assert r.json()["code"] == 404

    def test_delete_entry(self, client):
        r = self._create_entry(client)
        entry_id = r.json()["data"]["id"]
        r = client.delete(f"/api/entries/{entry_id}")
        assert r.json()["code"] == 0

    def test_delete_nonexistent(self, client):
        r = client.delete("/api/entries/99999")
        assert r.json()["code"] == 404

    def test_search_entries(self, client):
        self._create_entry(client, content="Python开发")
        self._create_entry(client, content="Java学习")
        r = client.get("/api/entries/search", params={"q": "Python"})
        body = r.json()
        assert body["code"] == 0
        assert any("Python" in e["content"] for e in body["data"])

    def test_filter_by_category(self, client):
        self._create_entry(client, content="跑步", category="运动")
        self._create_entry(client, content="写代码", category="编程")
        r = client.get("/api/entries", params={"category": "运动"})
        body = r.json()
        items = body["data"]["items"]
        for e in items:
            assert e["category"]["name"] == "运动"

    def test_filter_by_status(self, client):
        self._create_entry(client, content="完成了", status="completed")
        self._create_entry(client, content="没完成", status="incomplete")
        r = client.get("/api/entries", params={"status": "completed"})
        body = r.json()
        for e in body["data"]["items"]:
            assert e["status"] == "completed"


# ══════════════════════════════════════════════════════════════
# Categories
# ══════════════════════════════════════════════════════════════


class TestCategories:
    def test_list_categories(self, client):
        r = client.get("/api/categories")
        body = r.json()
        assert body["code"] == 0
        names = [c["name"] for c in body["data"]]
        assert "学习" in names
        assert "编程" in names

    def test_create_category(self, client):
        r = client.post("/api/categories", json={
            "name": "测试分类", "icon": "🧪", "color": "#FF0000",
        })
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["name"] == "测试分类"

    def test_create_duplicate_category(self, client):
        r = client.post("/api/categories", json={"name": "学习"})
        assert r.json()["code"] == 409

    def test_update_category(self, client):
        # 获取已有分类 ID
        r = client.get("/api/categories")
        cat_id = r.json()["data"][0]["id"]
        r = client.put(f"/api/categories/{cat_id}", json={"icon": "🎯"})
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["icon"] == "🎯"

    def test_delete_category(self, client):
        # 先创建再删除
        r = client.post("/api/categories", json={"name": "临时分类"})
        cat_id = r.json()["data"]["id"]
        r = client.delete(f"/api/categories/{cat_id}")
        assert r.json()["code"] == 0


# ══════════════════════════════════════════════════════════════
# Stats
# ══════════════════════════════════════════════════════════════


class TestStats:
    def _seed(self, client):
        """创建一些测试数据"""
        entries = [
            {"date": "2026-03-20", "content": "跑步", "category": "运动", "status": "completed"},
            {"date": "2026-03-20", "content": "写代码", "category": "编程", "status": "completed"},
            {"date": "2026-03-21", "content": "读书", "category": "学习", "status": "completed"},
            {"date": "2026-03-21", "content": "摸鱼", "category": "休息", "status": "incomplete"},
        ]
        for e in entries:
            client.post("/api/entries", json={**e, "source": "web"})

    def test_daily_stats(self, client):
        self._seed(client)
        r = client.get("/api/stats/daily", params={"date": "2026-03-21"})
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["total"] == 2

    def test_daily_stats_default_today(self, client):
        r = client.get("/api/stats/daily")
        assert r.json()["code"] == 0

    def test_heatmap(self, client):
        self._seed(client)
        r = client.get("/api/stats/heatmap", params={"year": 2026})
        body = r.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    def test_category_stats(self, client):
        self._seed(client)
        r = client.get("/api/stats/category", params={
            "start": "2026-03-01", "end": "2026-03-31",
        })
        body = r.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    def test_trend(self, client):
        self._seed(client)
        r = client.get("/api/stats/trend", params={
            "start": "2026-03-01", "end": "2026-03-31", "interval": "day",
        })
        body = r.json()
        assert body["code"] == 0

    def test_trend_week(self, client):
        self._seed(client)
        r = client.get("/api/stats/trend", params={
            "start": "2026-01-01", "end": "2026-03-31", "interval": "week",
        })
        assert r.json()["code"] == 0

    def test_trend_month(self, client):
        self._seed(client)
        r = client.get("/api/stats/trend", params={
            "start": "2026-01-01", "end": "2026-12-31", "interval": "month",
        })
        assert r.json()["code"] == 0

    def test_completion(self, client):
        self._seed(client)
        r = client.get("/api/stats/completion", params={
            "start": "2026-03-01", "end": "2026-03-31",
        })
        body = r.json()
        assert body["code"] == 0

    def test_streak(self, client):
        r = client.get("/api/stats/streak")
        body = r.json()
        assert body["code"] == 0
        assert "current_streak" in body["data"]
        assert "longest_streak" in body["data"]

    def test_yearly_summary(self, client):
        self._seed(client)
        r = client.get("/api/stats/yearly-summary", params={"year": 2026})
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["year"] == 2026
        assert body["data"]["total"] >= 4


# ══════════════════════════════════════════════════════════════
# Import
# ══════════════════════════════════════════════════════════════


class TestImport:
    def test_import_status(self, client):
        r = client.get("/api/import/status")
        body = r.json()
        assert body["code"] == 0
        assert "running" in body["data"]

    def test_import_history(self, client):
        r = client.get("/api/import/history")
        body = r.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)

    def test_import_invalid_path(self, client):
        r = client.post("/api/import/excel", data={
            "file_path": "/nonexistent/path.xlsx",
        })
        body = r.json()
        assert body["code"] == 400
