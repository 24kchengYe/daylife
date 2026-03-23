"""DayLife MCP Server 模块

提供 MCP (Model Context Protocol) 接口，让 Claude Code / Claude Desktop
可以通过自然语言记录和查询每日活动。

启动方式:
    python -m daylife.mcp
"""

from daylife.mcp.server import mcp

__all__ = ["mcp"]
