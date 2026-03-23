"""共享 LLM 客户端工具 — 提取自 classify.py，全项目复用"""

import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env (llm.py -> core -> daylife -> src -> daily-tracker)
_project_root = Path(__file__).resolve().parent.parent.parent.parent
for _p in [_project_root / ".env", Path.cwd() / ".env"]:
    if _p.exists():
        load_dotenv(_p, override=True)
        break


def get_llm_client(model_override: str | None = None):
    """创建 OpenAI 兼容客户端（支持代理自动检测）

    Args:
        model_override: 覆盖默认模型名称，如 "anthropic/claude-sonnet-4-5"

    Returns:
        (client, model) 元组。若未配置 API Key 则返回 (None, None)
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
    if not api_key:
        return None, None

    from openai import OpenAI

    proxy = (
        os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
        or os.getenv("ALL_PROXY") or os.getenv("https_proxy")
        or os.getenv("http_proxy") or os.getenv("all_proxy")
    )
    # Fallback: 检测本地常用代理端口
    if not proxy:
        import socket
        for port in [2080, 7890, 1080]:
            try:
                s = socket.create_connection(("127.0.0.1", port), timeout=0.5)
                s.close()
                proxy = f"http://127.0.0.1:{port}"
                break
            except Exception:
                continue
    http_client = None
    if proxy:
        try:
            import httpx
            http_client = httpx.Client(proxy=proxy)
            print(f"[LLM] Using proxy: {proxy}")
        except Exception:
            pass

    model = model_override or os.getenv("OPENAI_MODEL", "deepseek/deepseek-chat")
    client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
    return client, model
