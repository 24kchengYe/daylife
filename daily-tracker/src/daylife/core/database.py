"""数据库初始化与连接管理"""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from daylife.core.models import Base, Category

DEFAULT_DB_DIR = Path.home() / ".local" / "share" / "daylife"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "daylife.db"

# 预定义分类
DEFAULT_CATEGORIES = [
    {"name": "学习", "icon": "📚", "color": "#4A90D9", "sort_order": 1},
    {"name": "科研", "icon": "🔬", "color": "#7B68EE", "sort_order": 2},
    {"name": "编程", "icon": "💻", "color": "#00BCD4", "sort_order": 3},
    {"name": "运动", "icon": "🏃", "color": "#2ECC71", "sort_order": 4},
    {"name": "生活", "icon": "🏠", "color": "#F39C12", "sort_order": 5},
    {"name": "社交", "icon": "👥", "color": "#FF6B6B", "sort_order": 6},
    {"name": "工作", "icon": "💼", "color": "#E74C3C", "sort_order": 7},
    {"name": "娱乐", "icon": "🎮", "color": "#9B59B6", "sort_order": 8},
    {"name": "休息", "icon": "😴", "color": "#95A5A6", "sort_order": 9},
    {"name": "其他", "icon": "📝", "color": "#BDC3C7", "sort_order": 10},
]


def _enable_wal(dbapi_conn, connection_record):
    """启用 WAL 模式提升并发读性能，并开启外键约束"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db_path() -> Path:
    """获取数据库路径，优先使用环境变量"""
    env_path = os.environ.get("DAYLIFE_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


def create_db_engine(db_path: Path | None = None):
    """创建数据库引擎"""
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    event.listen(engine, "connect", _enable_wal)
    return engine


def init_db(engine=None) -> Session:
    """初始化数据库：建表 + 插入默认分类"""
    if engine is None:
        engine = create_db_engine()

    Base.metadata.create_all(engine)

    # 自动迁移：添加 ai_classified 列（如果不存在）
    with engine.connect() as conn:
        try:
            conn.execute(__import__("sqlalchemy").text(
                "ALTER TABLE daily_entries ADD COLUMN ai_classified INTEGER DEFAULT 0"
            ))
            conn.commit()
        except Exception:
            pass  # 列已存在

    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    # 插入默认分类（如果不存在）
    existing = session.query(Category).count()
    if existing == 0:
        for cat_data in DEFAULT_CATEGORIES:
            session.add(Category(**cat_data))
        session.commit()

    return session


def get_session(engine=None) -> Session:
    """获取数据库会话"""
    if engine is None:
        engine = create_db_engine()
    session_factory = sessionmaker(bind=engine)
    return session_factory()
