"""CLI 命令定义 - daily 命令行工具

用法：
    daily log '今天完成了XX' --category 科研 --tags paper,writing
    daily show [--date 2024-01-15] [--week] [--month]
    daily stats [--period week/month/year]
    daily search '关键词'
    daily import --path 'D:/my college/zyc学习计划/' [--dry-run]
    daily serve [--port 8061]
    daily mcp
    daily export --format json --start 2023-01-01 --end 2023-12-31
"""

import csv
import io
import json
from datetime import date, timedelta

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from daylife.core.database import init_db
from daylife.core.entry_service import EntryService
from daylife.core.schemas import EntryCreate, EntryQuery
from daylife.core.stats_service import StatsService

console = Console()


def _get_services(session=None):
    """获取数据库会话和服务实例"""
    if session is None:
        session = init_db()
    return session, EntryService(session), StatsService(session)


def _format_entry_table(entries, title: str) -> Table:
    """格式化条目列表为 Rich Table"""
    table = Table(title=title, show_lines=False)
    table.add_column("ID", style="dim", width=5)
    table.add_column("分类", width=8)
    table.add_column("内容", min_width=20)
    table.add_column("状态", width=4)
    table.add_column("时间", width=11)
    table.add_column("标签", style="cyan")

    status_icons = {
        "completed": "[green]V[/green]",
        "incomplete": "[red]X[/red]",
        "in_progress": "[yellow]~[/yellow]",
    }

    for e in entries:
        cat_str = f"{e.category.icon} {e.category.name}" if e.category else "-"
        s_icon = status_icons.get(e.status, "?")
        time_str = ""
        if e.start_time:
            time_str = e.start_time.strftime("%H:%M")
            if e.end_time:
                time_str += f"-{e.end_time.strftime('%H:%M')}"
        tags_str = ", ".join(t.name for t in e.tags) if e.tags else ""
        table.add_row(str(e.id), cat_str, e.content, s_icon, time_str, tags_str)

    return table


# ══════════════════════════════════════════════════════════════
# CLI Group
# ══════════════════════════════════════════════════════════════


@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="daylife")
@click.pass_context
def cli(ctx):
    """DayLife - 个人每日活动记录系统

    直接运行 daylife 即可启动 Web Dashboard 并打开浏览器。
    """
    if ctx.invoked_subcommand is None:
        ctx.invoke(serve)


# ══════════════════════════════════════════════════════════════
# daily log
# ══════════════════════════════════════════════════════════════


@cli.command()
@click.argument("content")
@click.option("-c", "--category", default=None,
              help="分类名（学习/科研/编程/运动/生活/社交/工作/娱乐/休息/其他）")
@click.option("-t", "--tags", default=None, help="标签，逗号分隔，如 paper,writing")
@click.option("-p", "--priority", default=3, type=int, help="优先级 1-5（默认3）")
@click.option("-s", "--status", default="completed",
              type=click.Choice(["completed", "incomplete", "in_progress"]),
              help="状态（默认completed）")
@click.option("-d", "--date", "entry_date", default=None, help="日期 YYYY-MM-DD（默认今天）")
@click.option("--start", default=None, help="开始时间 HH:MM")
@click.option("--end", default=None, help="结束时间 HH:MM")
@click.option("-n", "--notes", default=None, help="备注")
def log(content, category, tags, priority, status, entry_date, start, end, notes):
    """记录一条活动

    示例：
        daily log '完成论文第三章' --category 科研 --tags paper,writing
        daily log '跑步5公里' -c 运动 --start 07:00 --end 07:40
    """
    from datetime import time as dt_time

    session, entry_svc, _ = _get_services()

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    entry_data = EntryCreate(
        date=date.fromisoformat(entry_date) if entry_date else date.today(),
        category=category,
        content=content,
        status=status,
        start_time=dt_time.fromisoformat(start) if start else None,
        end_time=dt_time.fromisoformat(end) if end else None,
        priority=priority,
        tags=tag_list,
        notes=notes,
        source="cli",
    )

    entry = entry_svc.add_entry(entry_data)
    cat_str = f" [{entry.category.name}]" if entry.category else ""
    console.print(f"[green]V[/green] 已记录{cat_str}: {entry.content} (ID: {entry.id})")
    session.close()


# ══════════════════════════════════════════════════════════════
# daily show
# ══════════════════════════════════════════════════════════════


@cli.command()
@click.option("-d", "--date", "target_date", default=None, help="指定日期 YYYY-MM-DD（默认今天）")
@click.option("-w", "--week", is_flag=True, help="显示本周记录")
@click.option("-m", "--month", is_flag=True, help="显示本月记录")
def show(target_date, week, month):
    """查看活动记录

    示例：
        daily show                    # 今天
        daily show -d 2024-01-15      # 指定日期
        daily show --week             # 本周
        daily show --month            # 本月
    """
    session, entry_svc, stats_svc = _get_services()

    if week:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        entries = entry_svc.get_entries_by_date_range(week_start, week_end)
        title = f"本周 {week_start} ~ {week_end}"

        if not entries:
            console.print("[dim]本周还没有记录[/dim]")
        else:
            console.print(_format_entry_table(entries, title))

        summary = stats_svc.get_weekly_summary(week_start)
        console.print(
            f"\n  合计 [bold]{summary['total']}[/bold] 条 | "
            f"完成 [green]{summary['completed']}[/green] | "
            f"活跃 {summary['active_days']}/7 天 | "
            f"时长 {summary['total_minutes']} 分钟"
        )

    elif month:
        today = date.today()
        month_start = today.replace(day=1)
        if today.month == 12:
            month_end = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(today.year, today.month + 1, 1) - timedelta(days=1)

        entries = entry_svc.get_entries_by_date_range(month_start, month_end)
        title = f"{today.year}年{today.month}月"

        if not entries:
            console.print(f"[dim]{title} 还没有记录[/dim]")
        else:
            console.print(_format_entry_table(entries, title))

        summary = stats_svc.get_monthly_summary(today.year, today.month)
        console.print(
            f"\n  合计 [bold]{summary['total']}[/bold] 条 | "
            f"完成 [green]{summary['completed']}[/green] | "
            f"活跃 {summary['active_days']}/{summary['total_days']} 天 | "
            f"时长 {summary['total_minutes']} 分钟"
        )

    else:
        d = date.fromisoformat(target_date) if target_date else date.today()
        entries = entry_svc.get_entries_by_date(d)

        if not entries:
            console.print(f"[dim]{d} 没有记录[/dim]")
        else:
            console.print(_format_entry_table(entries, str(d)))

    session.close()


# ══════════════════════════════════════════════════════════════
# daily stats
# ══════════════════════════════════════════════════════════════


@cli.command()
@click.option("-p", "--period", default="week",
              type=click.Choice(["day", "week", "month", "year", "all"]),
              help="统计周期（默认week）")
@click.option("-d", "--date", "ref_date", default=None, help="参考日期 YYYY-MM-DD")
def stats(period, ref_date):
    """查看统计信息

    示例：
        daily stats                   # 本周统计
        daily stats -p month          # 本月统计
        daily stats -p year           # 今年统计
        daily stats -p all            # 全部统计
    """
    session, _, stats_svc = _get_services()

    ref = date.fromisoformat(ref_date) if ref_date else date.today()

    console.print()

    if period == "day":
        s = stats_svc.get_daily_summary(ref)
        console.print(Panel(
            f"  总记录:   [bold]{s['total']}[/bold]\n"
            f"  已完成:   [green]{s['completed']}[/green]\n"
            f"  未完成:   [red]{s['incomplete']}[/red]\n"
            f"  完成率:   {s['completion_rate']}%\n"
            f"  总时长:   {s['total_minutes']} 分钟\n"
            f"  分类分布: {', '.join(f'{k}({v})' for k, v in s['by_category'].items())}",
            title=f"日统计 {ref}",
        ))

    elif period == "week":
        week_start = ref - timedelta(days=ref.weekday())
        s = stats_svc.get_weekly_summary(week_start)
        console.print(Panel(
            f"  总记录:   [bold]{s['total']}[/bold]\n"
            f"  已完成:   [green]{s['completed']}[/green]\n"
            f"  完成率:   {s['completion_rate']}%\n"
            f"  活跃天数: {s['active_days']}/7\n"
            f"  总时长:   {s['total_minutes']} 分钟",
            title=f"周统计 {s['week_start']} ~ {s['week_end']}",
        ))

    elif period == "month":
        s = stats_svc.get_monthly_summary(ref.year, ref.month)
        console.print(Panel(
            f"  总记录:   [bold]{s['total']}[/bold]\n"
            f"  已完成:   [green]{s['completed']}[/green]\n"
            f"  完成率:   {s['completion_rate']}%\n"
            f"  活跃天数: {s['active_days']}/{s['total_days']}\n"
            f"  总时长:   {s['total_minutes']} 分钟",
            title=f"月统计 {ref.year}年{ref.month}月",
        ))

    elif period == "year":
        s = stats_svc.get_yearly_summary(ref.year)
        console.print(Panel(
            f"  总记录:   [bold]{s['total']}[/bold]\n"
            f"  已完成:   [green]{s['completed']}[/green]\n"
            f"  完成率:   {s['completion_rate']}%\n"
            f"  活跃天数: {s['active_days']}\n"
            f"  总时长:   {s['total_minutes']} 分钟\n"
            f"  月分布:   {', '.join(f'{m}月({c})' for m, c in sorted(s['monthly_counts'].items()))}",
            title=f"年统计 {ref.year}",
        ))

    elif period == "all":
        s = stats_svc.get_overview()
        streak = stats_svc.get_current_streak()
        longest = stats_svc.get_longest_streak()
        console.print(Panel(
            f"  总记录:     [bold]{s['total_entries']}[/bold]\n"
            f"  已完成:     [green]{s['completed_entries']}[/green]\n"
            f"  完成率:     {s['completion_rate']}%\n"
            f"  活跃天数:   {s['total_days']}\n"
            f"  总时长:     {s['total_minutes']} 分钟\n"
            f"  最活跃分类: {s['most_active_category'] or '-'}\n"
            f"  当前连续:   {streak} 天\n"
            f"  最长连续:   {longest['days']} 天",
            title="全部统计",
        ))

    session.close()


# ══════════════════════════════════════════════════════════════
# daily search
# ══════════════════════════════════════════════════════════════


@cli.command()
@click.argument("keyword")
@click.option("--from", "date_from", default=None, help="起始日期 YYYY-MM-DD")
@click.option("--to", "date_to", default=None, help="结束日期 YYYY-MM-DD")
@click.option("-c", "--category", default=None, help="分类筛选")
@click.option("-n", "--limit", default=20, type=int, help="最大返回条数")
def search(keyword, date_from, date_to, category, limit):
    """搜索活动记录

    示例：
        daily search '论文'
        daily search '运动' --from 2024-01-01 --to 2024-06-30
        daily search 'Python' -c 编程
    """
    session, entry_svc, _ = _get_services()

    query = EntryQuery(
        keyword=keyword,
        date_from=date.fromisoformat(date_from) if date_from else None,
        date_to=date.fromisoformat(date_to) if date_to else None,
        category=category,
        page_size=limit,
    )
    entries = entry_svc.search(query)

    if not entries:
        console.print(f'[dim]未找到包含 "{keyword}" 的记录[/dim]')
        session.close()
        return

    console.print(f'\n[bold]搜索 "{keyword}" 找到 {len(entries)} 条记录[/bold]\n')
    console.print(_format_entry_table(entries, f'搜索: "{keyword}"'))
    session.close()


# ══════════════════════════════════════════════════════════════
# daily import
# ══════════════════════════════════════════════════════════════


@cli.command("import")
@click.option("--path", required=True, help="Excel 文件或目录路径")
@click.option("--dry-run", is_flag=True, help="仅预览不写入数据库")
@click.option("--probe", is_flag=True, help="仅探测文件结构")
@click.option("--db-path", default=None, help="自定义数据库路径")
@click.option("-v", "--verbose", is_flag=True, help="详细日志")
def import_cmd(path, dry_run, probe, db_path, verbose):
    """导入 Excel 历史数据

    示例：
        daily import --path 'D:/my college/zyc学习计划/' --dry-run
        daily import --path data.xlsx --probe
        daily import --path 'D:/my college/zyc学习计划/'
    """
    import logging
    from pathlib import Path

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if db_path:
        import os
        os.environ["DAYLIFE_DB_PATH"] = db_path

    session = None
    if not dry_run and not probe:
        session = init_db()

    target = Path(path)

    from daylife.importer.excel_importer import ExcelImporter, import_directory

    if target.is_dir():
        import_directory(str(target), dry_run=dry_run, probe_only=probe, session=session)
    elif target.is_file() and target.suffix == ".xlsx":
        importer = ExcelImporter(session=session)
        if probe:
            result = importer.probe(str(target))
            console.print_json(json.dumps(result, ensure_ascii=False, default=str))
        elif dry_run:
            entries = importer.preview(str(target))
            console.print(f"[bold]预览: 将导入 {len(entries)} 条记录[/bold]\n")
            for entry in entries[:10]:
                console.print(
                    f"  [{entry['date']}] {entry['content'][:60]}  "
                    f"({entry['status']}, {entry['category']})"
                )
            if len(entries) > 10:
                console.print(f"  ... 还有 {len(entries) - 10} 条")
        else:
            result = importer.execute(str(target))
            console.print(
                f"[green]V[/green] 导入完成: {result.rows_imported} 条, "
                f"跳过: {result.rows_skipped} 条"
            )
            if result.errors:
                for err in result.errors[:5]:
                    console.print(f"  [red]错误:[/red] {err}")
    else:
        console.print(f"[red]错误:[/red] {target} 不是有效的文件或目录")
        raise SystemExit(1)


# ══════════════════════════════════════════════════════════════
# daily serve
# ══════════════════════════════════════════════════════════════


@cli.command()
@click.option("-p", "--port", default=8063, type=int, help="端口号（默认8063）")
@click.option("-h", "--host", "bind_host", default="127.0.0.1", help="绑定地址（默认127.0.0.1）")
@click.option("--reload", is_flag=True, help="开发模式热重载")
def serve(port, bind_host, reload):
    """启动 Web Dashboard

    示例：
        daily serve
        daily serve --port 9000
        daily serve --host 0.0.0.0 --reload
    """
    import uvicorn

    init_db()
    url = f"http://{bind_host}:{port}"
    console.print(f"[bold green]DayLife Web Dashboard[/bold green] -> {url}")
    uvicorn.run("daylife.api.main:app", host=bind_host, port=port, reload=reload)


# ══════════════════════════════════════════════════════════════
# daily tray
# ══════════════════════════════════════════════════════════════


@cli.command()
@click.option("-p", "--port", default=8063, type=int, help="端口号")
def tray(port):
    """托盘模式：后台服务 + 系统托盘图标

    服务常驻后台，托盘图标点击打开浏览器。适合开机自启。
    """
    from daylife.tray import main as tray_main
    console.print(f"[bold green]DayLife 托盘模式[/bold green] -> http://127.0.0.1:{port}")
    tray_main(port=port)


# ══════════════════════════════════════════════════════════════
# daily mcp
# ══════════════════════════════════════════════════════════════


@cli.command()
def mcp():
    """启动 MCP Server（供 Claude Code 调用）"""
    from daylife.mcp.server import main as mcp_main
    mcp_main()


# ══════════════════════════════════════════════════════════════
# daily export
# ══════════════════════════════════════════════════════════════


@cli.command()
@click.option("-f", "--format", "fmt", default="markdown",
              type=click.Choice(["json", "csv", "markdown"]),
              help="导出格式（默认markdown）")
@click.option("--start", "start_date", required=True, help="起始日期 YYYY-MM-DD")
@click.option("--end", "end_date", required=True, help="结束日期 YYYY-MM-DD")
@click.option("-o", "--output", default=None, help="输出文件路径（默认输出到终端）")
@click.option("-c", "--category", default=None, help="按分类筛选")
def export(fmt, start_date, end_date, output, category):
    """导出活动记录

    示例：
        daily export --start 2023-01-01 --end 2023-12-31 -f json
        daily export --start 2024-01-01 --end 2024-03-31 -f csv -o data.csv
        daily export --start 2024-01-01 --end 2024-01-31 -f markdown
    """
    session, entry_svc, _ = _get_services()

    d_from = date.fromisoformat(start_date)
    d_to = date.fromisoformat(end_date)
    entries = entry_svc.get_entries_by_date_range(d_from, d_to, category=category)

    if not entries:
        console.print("[dim]指定范围内没有记录[/dim]")
        session.close()
        return

    def _entry_dict(e):
        return {
            "id": e.id,
            "date": e.date.isoformat(),
            "category": e.category.name if e.category else None,
            "content": e.content,
            "status": e.status,
            "start_time": e.start_time.strftime("%H:%M") if e.start_time else None,
            "end_time": e.end_time.strftime("%H:%M") if e.end_time else None,
            "duration_minutes": e.duration_minutes,
            "priority": e.priority,
            "tags": ", ".join(t.name for t in e.tags) if e.tags else "",
            "notes": e.notes or "",
        }

    if fmt == "json":
        data = [_entry_dict(e) for e in entries]
        text = json.dumps(data, ensure_ascii=False, indent=2)

    elif fmt == "csv":
        buf = io.StringIO()
        fields = ["id", "date", "category", "content", "status",
                  "start_time", "end_time", "duration_minutes", "priority", "tags", "notes"]
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()
        for e in entries:
            writer.writerow(_entry_dict(e))
        text = buf.getvalue()

    else:  # markdown
        lines = [f"# DayLife 导出 {d_from} ~ {d_to}\n"]
        current_day = None
        for e in entries:
            if e.date != current_day:
                current_day = e.date
                lines.append(f"\n## {current_day}\n")
            cat_str = f"[{e.category.name}] " if e.category else ""
            status_str = {"completed": "V", "incomplete": "X", "in_progress": "~"}.get(
                e.status, "?"
            )
            time_str = ""
            if e.start_time:
                time_str = f" ({e.start_time.strftime('%H:%M')}"
                if e.end_time:
                    time_str += f"-{e.end_time.strftime('%H:%M')}"
                time_str += ")"
            tags_str = f" `{', '.join(t.name for t in e.tags)}`" if e.tags else ""
            lines.append(f"- [{status_str}] {cat_str}{e.content}{time_str}{tags_str}")
        text = "\n".join(lines) + "\n"

    if output:
        from pathlib import Path
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            f.write(text)
        console.print(f"[green]V[/green] 已导出 {len(entries)} 条记录到 {output}")
    else:
        console.print(text)

    session.close()
