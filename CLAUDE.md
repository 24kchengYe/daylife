# 每日记录系统 (daylife)

基于 MCP Server + 本地 Web Dashboard 的个人每日活动记录系统，导入 7-8 年历史 Excel 数据。

## 项目由 ccTask 自动创建

本项目通过 ccTask（AI 任务执行器）自动生成并开发，共 8 个任务阶段。

## 项目结构

```
061daylife/
└── daily-tracker/           ← 主项目目录
    ├── src/daylife/
    │   ├── core/            ← 数据库模型、CRUD、服务层
    │   ├── importer/        ← Excel 历史数据导入器
    │   ├── mcp/             ← MCP Server（Claude Code 集成）
    │   ├── api/             ← FastAPI Web Dashboard 后端
    │   └── cli/             ← CLI 快捷记录工具
    ├── tests/               ← 测试
    ├── ARCHITECTURE.md      ← 架构设计文档
    └── README.md            ← 使用说明
```

## 开发进度

查看 `daily-tracker/PROGRESS.md` 了解每个任务阶段做了什么、当前状态和下一步建议。

## 详细操作日志

每个任务的完整 AI 操作记录（包括所有命令、文件读写、AI 思考过程）在：
`D:/pythonPycharms/工具开发/ccTaskLog/每日记录系统/`

日志格式为 JSONL（每行一个 JSON 事件），文件名如 `detail_01_20260321_134242.jsonl`。

## 队列配置

任务队列定义在：`D:/pythonPycharms/工具开发/ccTask/queues/061-daylife.json`

## 历史数据位置

用户的 7-8 年历史 Excel 记录在：`D:\my college\zyc学习计划`
- 灰色单元格 = 已完成
- 红色单元格 = 未完成
- 时间校准：大一 2018.9 入学，博一 2023.9 入学（Excel 中的日期可能因公式显示为当前日期，需推算真实时间）

## 技术栈

- Python + FastAPI + SQLite + SQLAlchemy
- Vue 3 + ECharts（前端 Dashboard）
- MCP Server（Claude Code 集成）
- Click（CLI 工具）
- openpyxl（Excel 导入）
