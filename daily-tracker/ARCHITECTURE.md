# DayLife - 个人每日活动记录系统 架构文档

## 项目概述

DayLife 是一个本地优先（local-first）的个人每日活动记录与分析系统。支持通过 CLI、MCP Server、Web Dashboard 三种方式记录和查看每日活动。

**设计哲学**：
- 参考 jrnl 的极简 CLI 交互体验
- 借鉴 ActivityWatch 的 SQLite + REST API + Vue.js WebUI 架构
- 学习 Logseq 的"每日自动日志页"UX 模式
- 采用 Traggo 的结构化标签（typed key-value）用于多维分析

---

## 1. 技术栈

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| **后端框架** | FastAPI | 异步高性能，自动 OpenAPI 文档，便于 MCP 集成 |
| **数据库** | SQLite (WAL mode) | 本地优先，零运维，单文件便携，支持并发读 |
| **ORM** | SQLAlchemy 2.0 | 成熟稳定，支持异步（aiosqlite） |
| **前端框架** | Vue 3 + Vite | 响应式，轻量，生态成熟 |
| **可视化** | ECharts | 日历热力图、趋势图、分类饼图一站式解决 |
| **MCP Server** | mcp Python SDK | 供 Claude Code 直接调用记录/查询 |
| **CLI** | Click | Python CLI 标准选择，支持子命令 |
| **Excel 解析** | openpyxl | 支持读取单元格颜色（用于解析完成状态标记） |

---

## 2. 数据模型

### 2.1 ER 关系图

```
categories 1──N daily_entries N──N tags (via entry_tags)
                    │
                    1
                    │
                    N
               attachments

import_metadata (独立表，记录导入历史)
```

### 2.2 表设计

#### `categories` - 活动分类

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| name | TEXT UNIQUE | 分类名（学习、科研、运动、生活等） |
| icon | TEXT | Emoji 图标 |
| color | TEXT | 十六进制颜色码，用于前端展示 |
| sort_order | INTEGER | 排序权重 |
| created_at | TIMESTAMP | 创建时间 |

**预定义分类**：
- 📚 学习 `#4A90D9`
- 🔬 科研 `#7B68EE`
- 🏃 运动 `#2ECC71`
- 🏠 生活 `#F39C12`
- 💼 工作 `#E74C3C`
- 🎮 娱乐 `#9B59B6`
- 😴 休息 `#95A5A6`
- 📝 其他 `#BDC3C7`

#### `daily_entries` - 每日活动记录（核心表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| date | DATE NOT NULL | 日期（索引） |
| category_id | INTEGER FK | 关联分类 |
| content | TEXT NOT NULL | 活动内容描述 |
| status | TEXT | `completed` / `incomplete` / `in_progress` |
| start_time | TIME | 开始时间（可选） |
| end_time | TIME | 结束时间（可选） |
| duration_minutes | INTEGER | 持续时长（分钟），可由 start/end 计算或手动填写 |
| priority | INTEGER | 优先级 1-5（5最高） |
| notes | TEXT | 备注 |
| data_json | TEXT | 扩展字段，JSON 格式（参考 ActivityWatch） |
| source | TEXT | 来源：`cli` / `mcp` / `web` / `excel_import` |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

索引：`(date)`, `(date, category_id)`, `(status)`

#### `tags` - 标签

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| name | TEXT UNIQUE | 标签名 |
| color | TEXT | 颜色 |

#### `entry_tags` - 记录-标签关联（多对多）

| 字段 | 类型 | 说明 |
|------|------|------|
| entry_id | INTEGER FK | 关联 daily_entries |
| tag_id | INTEGER FK | 关联 tags |

复合主键：`(entry_id, tag_id)`

#### `attachments` - 附件

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| entry_id | INTEGER FK | 关联 daily_entries |
| file_path | TEXT | 文件路径 |
| file_type | TEXT | MIME 类型 |
| file_size | INTEGER | 文件大小（字节） |
| created_at | TIMESTAMP | 创建时间 |

#### `import_metadata` - 导入记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| source_file | TEXT | 源文件路径 |
| import_type | TEXT | `excel` / `csv` / `json` |
| rows_imported | INTEGER | 导入行数 |
| rows_skipped | INTEGER | 跳过行数 |
| date_range_start | DATE | 数据最早日期 |
| date_range_end | DATE | 数据最晚日期 |
| color_mapping | TEXT | 颜色→状态映射规则（JSON） |
| imported_at | TIMESTAMP | 导入时间 |
| notes | TEXT | 备注 |

---

## 3. 核心功能

### 3.1 Excel 历史数据导入

解析用户已有的 Excel 每日记录表，支持：
- 读取单元格背景颜色映射完成状态（灰色=completed，红色=incomplete，无色=in_progress）
- 自动识别日期列、内容列、分类列
- 可配置的颜色-状态映射规则
- 导入前预览 + 冲突处理（跳过/覆盖/合并）
- 记录导入元信息到 `import_metadata` 表

### 3.2 MCP Server 接口

供 Claude Code 直接调用，工具列表：

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `log_activity` | 记录一条活动 | date, category, content, status, start_time, end_time, tags, priority |
| `get_today` | 获取今日所有活动 | - |
| `get_daily_summary` | 获取指定日期摘要 | date |
| `search_entries` | 搜索活动记录 | keyword, date_from, date_to, category, status, tags |
| `get_stats` | 获取统计数据 | period (week/month/year), category |
| `update_entry` | 更新一条记录 | entry_id, fields... |
| `delete_entry` | 删除一条记录 | entry_id |
| `list_categories` | 列出所有分类 | - |

### 3.3 Web Dashboard

本地 Web 界面，访问 `http://localhost:8061`：

- **日历热力图**：按天着色显示活动密度（参考 GitHub Contribution Graph）
- **日视图**：时间线展示当天活动块（参考 ActivityWatch Timeline）
- **分类统计**：饼图/环形图展示各分类时间占比
- **趋势分析**：折线图展示周/月活动量变化趋势
- **标签云**：高频标签可视化
- **完成率追踪**：按分类/按周的任务完成率

### 3.4 CLI 快捷记录

```bash
# 快速记录
daylife log "完成论文第三章初稿" -c 科研 -t 论文 写作 -p 5

# 查看今天
daylife today

# 查看指定日期
daylife show 2026-03-20

# 搜索
daylife search "论文" --from 2026-03-01 --to 2026-03-21

# 统计
daylife stats --period month

# 导入 Excel
daylife import data.xlsx --sheet "3月" --preview

# 启动 Web 服务
daylife serve
```

---

## 4. 目录结构

```
daily-tracker/
├── ARCHITECTURE.md          # 本文档
├── README.md                # 项目说明
├── pyproject.toml           # 项目配置 & 依赖
├── requirements.txt         # pip 依赖（兼容）
├── .gitignore
│
├── src/
│   └── daylife/
│       ├── __init__.py
│       ├── __main__.py      # python -m daylife 入口
│       │
│       ├── core/            # 核心业务逻辑
│       │   ├── __init__.py
│       │   ├── models.py    # SQLAlchemy 模型定义
│       │   ├── database.py  # 数据库初始化 & 连接管理
│       │   ├── service.py   # 业务服务层（CRUD + 统计）
│       │   └── schemas.py   # Pydantic 数据校验模型
│       │
│       ├── api/             # FastAPI 路由
│       │   ├── __init__.py
│       │   ├── app.py       # FastAPI 应用实例
│       │   ├── entries.py   # /api/entries 路由
│       │   ├── categories.py # /api/categories 路由
│       │   ├── stats.py     # /api/stats 路由
│       │   └── imports.py   # /api/import 路由
│       │
│       ├── cli/             # CLI 命令
│       │   ├── __init__.py
│       │   └── commands.py  # Click 命令定义
│       │
│       ├── mcp/             # MCP Server
│       │   ├── __init__.py
│       │   └── server.py    # MCP 工具注册 & 处理
│       │
│       ├── importer/        # 数据导入
│       │   ├── __init__.py
│       │   ├── excel.py     # Excel 导入（openpyxl，解析颜色）
│       │   └── base.py      # 导入基类
│       │
│       └── web/             # 前端静态文件（构建产物）
│           └── dist/        # Vue 构建输出
│
├── frontend/                # Vue 3 前端源码
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.vue
│       ├── main.ts
│       ├── views/
│       │   ├── Dashboard.vue    # 主仪表盘
│       │   ├── Calendar.vue     # 日历热力图
│       │   ├── DayView.vue      # 日视图
│       │   └── Stats.vue        # 统计页
│       ├── components/
│       │   ├── HeatMap.vue      # 热力图组件
│       │   ├── Timeline.vue     # 时间线组件
│       │   ├── EntryForm.vue    # 记录表单
│       │   └── CategoryPie.vue  # 分类饼图
│       └── api/
│           └── client.ts        # API 客户端
│
├── data/                    # 数据目录（gitignored）
│   ├── daylife.db           # SQLite 数据库
│   └── attachments/         # 附件存储
│
└── tests/
    ├── __init__.py
    ├── test_models.py
    ├── test_service.py
    ├── test_api.py
    ├── test_importer.py
    └── test_cli.py
```

---

## 5. API 接口设计

Base URL: `http://localhost:8061/api`

### 5.1 活动记录 CRUD

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/entries` | 查询记录列表（支持 date/category/status/keyword 过滤） |
| `GET` | `/entries/{id}` | 获取单条记录 |
| `POST` | `/entries` | 创建记录 |
| `PUT` | `/entries/{id}` | 更新记录 |
| `DELETE` | `/entries/{id}` | 删除记录 |
| `GET` | `/entries/today` | 获取今日记录 |
| `GET` | `/entries/date/{date}` | 获取指定日期记录 |

**查询参数**（GET /entries）：
```
?date_from=2026-03-01
&date_to=2026-03-21
&category=科研
&status=completed
&keyword=论文
&tags=写作,论文
&page=1
&page_size=20
```

**请求体**（POST /entries）：
```json
{
  "date": "2026-03-21",
  "category": "科研",
  "content": "完成论文第三章初稿",
  "status": "completed",
  "start_time": "09:00",
  "end_time": "12:30",
  "priority": 5,
  "tags": ["论文", "写作"],
  "notes": "引用了3篇新参考文献"
}
```

### 5.2 分类

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/categories` | 列出所有分类 |
| `POST` | `/categories` | 创建分类 |
| `PUT` | `/categories/{id}` | 更新分类 |

### 5.3 统计

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/stats/overview` | 总览统计（总记录数、完成率、活跃天数） |
| `GET` | `/stats/heatmap` | 日历热力图数据（每日活动计数） |
| `GET` | `/stats/category` | 分类统计（各分类时间/数量占比） |
| `GET` | `/stats/trend` | 趋势数据（按周/月聚合） |
| `GET` | `/stats/tags` | 标签频次统计 |
| `GET` | `/stats/completion` | 完成率追踪 |

**热力图响应示例**：
```json
{
  "data": [
    {"date": "2026-03-21", "count": 8, "completed": 6, "total_minutes": 420},
    {"date": "2026-03-20", "count": 5, "completed": 5, "total_minutes": 360}
  ]
}
```

### 5.4 数据导入

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/import/excel` | 上传并导入 Excel 文件 |
| `POST` | `/import/excel/preview` | 预览导入结果（不写入） |
| `GET` | `/import/history` | 导入历史记录 |

### 5.5 标签

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/tags` | 列出所有标签 |
| `GET` | `/tags/popular` | 高频标签 |

---

## 6. 配置

配置文件：`~/.config/daylife/config.toml`

```toml
[database]
path = "~/.local/share/daylife/daylife.db"   # 数据库路径

[server]
host = "127.0.0.1"
port = 8061

[import.excel]
# 颜色→状态映射
[import.excel.color_mapping]
gray = "completed"       # 灰色背景 = 已完成
red = "incomplete"       # 红色背景 = 未完成
default = "in_progress"  # 无背景色 = 进行中

[mcp]
enabled = true
```

---

## 7. 开发路线

### Phase 1：核心基础 ✦
- [ ] 数据模型 + 数据库初始化
- [ ] 基础 CRUD 服务层
- [ ] FastAPI 路由
- [ ] CLI 基础命令（log, today, show）

### Phase 2：数据导入
- [ ] Excel 导入解析器（含颜色识别）
- [ ] 导入预览 + 冲突处理
- [ ] 导入历史记录

### Phase 3：MCP Server
- [ ] MCP 工具注册
- [ ] log_activity / get_today / search_entries
- [ ] Claude Code 集成测试

### Phase 4：Web Dashboard
- [ ] Vue 3 项目初始化
- [ ] 日历热力图（ECharts）
- [ ] 分类统计图表
- [ ] 日视图时间线
- [ ] 趋势分析图表

### Phase 5：增强功能
- [ ] 标签系统完善
- [ ] 数据导出（JSON/CSV/Markdown）
- [ ] 每日模板（参考 Logseq）
- [ ] 附件管理
