"""数据库初始化与连接管理"""

import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from daylife.core.models import Base, Category, Tag

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

# ── 模块级单例：连接池复用 ──
_engine = None
_SessionFactory = None


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
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
    )
    event.listen(engine, "connect", _enable_wal)
    return engine


def _get_engine():
    """获取或创建模块级单例引擎"""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def init_db(engine=None) -> Session:
    """初始化数据库：建表 + 插入默认分类 + 索引 + FTS5"""
    if engine is None:
        engine = _get_engine()

    Base.metadata.create_all(engine)

    # 自动迁移：添加缺失列（如果不存在）
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE daily_entries ADD COLUMN ai_classified INTEGER DEFAULT 0",
            "ALTER TABLE tags ADD COLUMN description TEXT",
            "ALTER TABLE reports ADD COLUMN formatted INTEGER DEFAULT 0",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # 列已存在

        # 添加索引（兼容已有数据库）
        for stmt in [
            "CREATE INDEX IF NOT EXISTS ix_de_category_id ON daily_entries (category_id)",
            "CREATE INDEX IF NOT EXISTS ix_de_status ON daily_entries (status)",
            "CREATE INDEX IF NOT EXISTS ix_de_date_category ON daily_entries (date, category_id)",
            "CREATE INDEX IF NOT EXISTS ix_de_date_status ON daily_entries (date, status)",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass

        # FTS5 全文搜索索引
        try:
            conn.execute(text("""
                CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
                    content,
                    content_rowid='id',
                    content='daily_entries',
                    tokenize='unicode61'
                )
            """))
            conn.commit()

            # 同步触发器
            for trigger_sql in [
                """CREATE TRIGGER IF NOT EXISTS entries_fts_ai AFTER INSERT ON daily_entries BEGIN
                    INSERT INTO entries_fts(rowid, content) VALUES (new.id, new.content);
                END""",
                """CREATE TRIGGER IF NOT EXISTS entries_fts_ad AFTER DELETE ON daily_entries BEGIN
                    INSERT INTO entries_fts(entries_fts, rowid, content) VALUES('delete', old.id, old.content);
                END""",
                """CREATE TRIGGER IF NOT EXISTS entries_fts_au AFTER UPDATE OF content ON daily_entries BEGIN
                    INSERT INTO entries_fts(entries_fts, rowid, content) VALUES('delete', old.id, old.content);
                    INSERT INTO entries_fts(rowid, content) VALUES (new.id, new.content);
                END""",
            ]:
                conn.execute(text(trigger_sql))
                conn.commit()

            # 一次性填充已有数据到 FTS 索引（如果 FTS 表为空但 entries 有数据）
            fts_count = conn.execute(text("SELECT COUNT(*) FROM entries_fts")).scalar()
            entry_count = conn.execute(text("SELECT COUNT(*) FROM daily_entries")).scalar()
            if fts_count == 0 and entry_count > 0:
                conn.execute(text(
                    "INSERT INTO entries_fts(rowid, content) SELECT id, content FROM daily_entries"
                ))
                conn.commit()
        except Exception:
            pass  # FTS5 不可用时不影响核心功能

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
    """获取数据库会话（复用单例连接池）"""
    global _SessionFactory
    if _SessionFactory is None:
        if engine is None:
            engine = _get_engine()
        _SessionFactory = sessionmaker(bind=engine)
    return _SessionFactory()
