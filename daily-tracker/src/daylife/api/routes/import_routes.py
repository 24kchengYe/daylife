"""数据导入路由 - Excel 导入触发与状态查询"""

import threading
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form

from daylife.core import crud
from daylife.core.database import get_session, init_db
from daylife.core.schemas import ApiResponse, ImportMetadataOut

router = APIRouter()

# 简单的导入状态跟踪（进程内）
_import_status: dict = {
    "running": False,
    "progress": None,
    "last_result": None,
}
_import_lock = threading.Lock()


@router.post("/excel", response_model=ApiResponse)
def import_excel(
    file_path: str = Form(..., description="Excel 文件或目录路径"),
    dry_run: bool = Form(False, description="仅预览不写入"),
):
    """触发 Excel 导入"""
    target = Path(file_path)
    if not target.exists():
        return ApiResponse(code=400, message=f"Path not found: {file_path}")

    with _import_lock:
        if _import_status["running"]:
            return ApiResponse(code=409, message="An import is already running")
        _import_status["running"] = True
        _import_status["progress"] = "starting"

    def _do_import():
        try:
            from daylife.importer.excel_importer import ExcelImporter, import_directory
            session = init_db()

            if target.is_dir():
                result = import_directory(
                    str(target), dry_run=dry_run, session=session,
                )
            else:
                importer = ExcelImporter(session=session)
                if dry_run:
                    entries = importer.preview(str(target))
                    result = {"total_imported": len(entries), "dry_run": True}
                else:
                    r = importer.execute(str(target))
                    result = {
                        "rows_imported": r.rows_imported,
                        "rows_skipped": r.rows_skipped,
                        "errors": r.errors,
                    }

            with _import_lock:
                _import_status["last_result"] = {
                    "finished_at": datetime.now().isoformat(),
                    **result,
                }
        except Exception as e:
            with _import_lock:
                _import_status["last_result"] = {
                    "finished_at": datetime.now().isoformat(),
                    "error": str(e),
                }
        finally:
            with _import_lock:
                _import_status["running"] = False
                _import_status["progress"] = None

    thread = threading.Thread(target=_do_import, daemon=True)
    thread.start()

    return ApiResponse(message="Import started")


@router.get("/status", response_model=ApiResponse)
def get_import_status():
    """查询当前导入状态"""
    with _import_lock:
        return ApiResponse(data={
            "running": _import_status["running"],
            "progress": _import_status["progress"],
            "last_result": _import_status["last_result"],
        })


@router.get("/history", response_model=ApiResponse[list[ImportMetadataOut]])
def get_import_history():
    """获取导入历史"""
    session = get_session()
    try:
        records = crud.list_import_records(session)
        items = [ImportMetadataOut.model_validate(r) for r in records]
        return ApiResponse(data=items)
    finally:
        session.close()
