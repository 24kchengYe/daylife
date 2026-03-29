"""启动 DayLife Web Dashboard API 服务

用法：
    python run_server.py
    python run_server.py --port 8061 --host 0.0.0.0
    python run_server.py --reload
"""

import argparse


def main():
    parser = argparse.ArgumentParser(description="DayLife API Server")
    parser.add_argument("--host", default="127.0.0.1", help="绑定地址 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8263, help="端口 (默认 8263)")
    parser.add_argument("--reload", action="store_true", help="开发模式热重载")
    args = parser.parse_args()

    import uvicorn
    uvicorn.run(
        "daylife.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
