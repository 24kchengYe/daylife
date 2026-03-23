"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from daylife.api.routes.entries import router as entries_router
from daylife.api.routes.stats import router as stats_router
from daylife.api.routes.categories import router as categories_router
from daylife.api.routes.import_routes import router as import_router
from daylife.api.routes.classify import router as classify_router
from daylife.api.routes.github import router as github_router
from daylife.core.database import init_db

# 前端静态文件目录
WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="DayLife API",
        description="个人每日活动记录系统 - Web Dashboard 后端",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://localhost:8063",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8063",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(entries_router, prefix="/api/entries", tags=["entries"])
    app.include_router(stats_router, prefix="/api/stats", tags=["stats"])
    app.include_router(categories_router, prefix="/api/categories", tags=["categories"])
    app.include_router(import_router, prefix="/api/import", tags=["import"])
    app.include_router(classify_router, prefix="/api/classify", tags=["classify"])
    app.include_router(github_router, prefix="/api/github", tags=["github"])

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    # 静态文件 (JS/CSS)
    if WEB_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

        @app.get("/")
        def serve_index():
            return FileResponse(str(WEB_DIR / "index.html"))

    return app


app = create_app()
