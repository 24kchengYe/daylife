"""DayLife 统一启动脚本

用法：
    python start.py            # 同时启动 Web Server 和 MCP Server
    python start.py --web-only # 只启动 Web Dashboard
    python start.py --mcp-only # 只启动 MCP Server
    python start.py --import   # 运行数据导入
"""

import argparse
import multiprocessing
import sys


def start_web(host: str, port: int):
    """启动 Web Dashboard"""
    import uvicorn
    from daylife.core.database import init_db

    init_db()
    print(f"[Web] DayLife Dashboard -> http://{host}:{port}")
    uvicorn.run("daylife.api.main:app", host=host, port=port)


def start_mcp():
    """启动 MCP Server"""
    from daylife.mcp.server import main as mcp_main

    print("[MCP] DayLife MCP Server starting (stdio)...")
    mcp_main()


def run_import(excel_path: str, dry_run: bool = False):
    """运行数据导入"""
    from daylife.core.database import init_db
    from daylife.importer.excel_importer import import_directory

    session = None if dry_run else init_db()
    import_directory(excel_path, dry_run=dry_run, session=session)


def main():
    parser = argparse.ArgumentParser(
        description="DayLife 统一启动器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
示例：
  python start.py                启动 Web + MCP
  python start.py --web-only     只启动 Web Dashboard
  python start.py --mcp-only     只启动 MCP Server
  python start.py --import       导入 Excel 数据
  python start.py --import --dry-run  预览导入（不写入）
""",
    )
    parser.add_argument("--web-only", action="store_true", help="只启动 Web Dashboard")
    parser.add_argument("--mcp-only", action="store_true", help="只启动 MCP Server")
    parser.add_argument("--import", dest="run_import", action="store_true", help="运行数据导入")
    parser.add_argument("--dry-run", action="store_true", help="导入预览模式（配合 --import）")
    parser.add_argument("--host", default="127.0.0.1", help="Web 绑定地址（默认 127.0.0.1）")
    parser.add_argument("--port", type=int, default=8263, help="Web 端口（默认 8263）")
    parser.add_argument(
        "--excel-path",
        default="D:/my college/zyc学习计划/",
        help="Excel 数据路径（配合 --import）",
    )

    args = parser.parse_args()

    # 确保 src 在 Python path 中
    from pathlib import Path
    src_dir = str(Path(__file__).resolve().parent / "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    if args.run_import:
        run_import(args.excel_path, dry_run=args.dry_run)
        return

    if args.mcp_only:
        start_mcp()
        return

    if args.web_only:
        start_web(args.host, args.port)
        return

    # 默认：同时启动 Web 和 MCP
    # Web 在主进程，MCP 在子进程
    print("=" * 50)
    print("  DayLife - 启动 Web Dashboard + MCP Server")
    print("=" * 50)
    print()

    mcp_proc = multiprocessing.Process(target=start_mcp, daemon=True)
    mcp_proc.start()

    try:
        start_web(args.host, args.port)
    except KeyboardInterrupt:
        print("\n[Shutdown] 正在停止...")
    finally:
        if mcp_proc.is_alive():
            mcp_proc.terminate()
            mcp_proc.join(timeout=3)


if __name__ == "__main__":
    main()
