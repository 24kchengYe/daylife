# DayLife MCP Server 配置指南

## 启动方式

```bash
# 方式1：模块方式启动（推荐）
python -m daylife.mcp

# 方式2：直接运行
python src/daylife/mcp/server.py
```

## Claude Code 配置

在项目根目录的 `.mcp.json` 中添加：

```json
{
  "mcpServers": {
    "daylife": {
      "command": "python",
      "args": ["-m", "daylife.mcp"],
      "cwd": "D:/pythonPycharms/工具开发/061daylife/daily-tracker",
      "env": {
        "PYTHONPATH": "D:/pythonPycharms/工具开发/061daylife/daily-tracker/src"
      }
    }
  }
}
```

或者使用 `uv`：

```json
{
  "mcpServers": {
    "daylife": {
      "command": "uv",
      "args": ["run", "--directory", "D:/pythonPycharms/工具开发/061daylife/daily-tracker", "python", "-m", "daylife.mcp"]
    }
  }
}
```

## Claude Desktop 配置

编辑 `%APPDATA%/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "daylife": {
      "command": "python",
      "args": ["-m", "daylife.mcp"],
      "env": {
        "PYTHONPATH": "D:/pythonPycharms/工具开发/061daylife/daily-tracker/src"
      }
    }
  }
}
```

## 自定义数据库路径

通过环境变量指定数据库文件位置：

```json
{
  "mcpServers": {
    "daylife": {
      "command": "python",
      "args": ["-m", "daylife.mcp"],
      "env": {
        "PYTHONPATH": "D:/pythonPycharms/工具开发/061daylife/daily-tracker/src",
        "DAYLIFE_DB_PATH": "D:/my-data/daylife.db"
      }
    }
  }
}
```

## 提供的 Tools

| Tool | 描述 | 参数 |
|------|------|------|
| `log_activity` | 记录一条活动 | content, category?, date?, time_slot?, tags?, status?, notes?, priority? |
| `query_day` | 查询某天的所有活动 | date? |
| `query_range` | 查询日期范围内的活动 | start_date, end_date, category? |
| `get_stats` | 获取统计信息 | period(day/week/month/year), date? |
| `search_entries` | 全文搜索历史记录 | keyword, limit? |
| `update_entry` | 修改某条记录 | entry_id, content?, category?, status?, tags?, notes?, priority?, time_slot? |
| `delete_entry` | 删除某条记录 | entry_id |
| `get_categories` | 获取所有分类 | - |
| `get_streak` | 获取连续记录天数 | - |
| `get_summary` | 生成时间段的活动总结 | start_date?, end_date?, period? |

## 提供的 Resources

| URI | 描述 |
|-----|------|
| `daily://today` | 今天的活动列表 |
| `daily://stats/week` | 本周统计 |
| `daily://stats/month` | 本月统计 |

## 使用示例（自然语言）

- "记录一下：今天上午9点到11点写了MCP代码，分类是编程"
- "今天做了什么？"
- "搜一下上周关于运动的记录"
- "这个月的统计看一下"
- "我连续打卡多少天了？"
- "把ID为5的记录改成已完成"
- "总结一下这周的活动"
