"""日期校正模块 - 根据Excel文件名中的学期信息推算真实年份

用户的Excel文件日期可能显示为当前年份（如2026），需要根据文件名中的
学期信息推算真实年份。

关键时间参照：大一入学2018年9月，博一入学2023年9月。
"""

import re
from datetime import date, datetime


# 学期 → 真实年份范围映射
# 格式: (start_year, start_month, end_year, end_month)
SEMESTER_YEAR_MAP: dict[str, tuple[int, int, int, int]] = {
    "大一上": (2018, 9, 2019, 1),
    "大一下": (2019, 3, 2019, 8),
    "大一寒假": (2019, 1, 2019, 2),
    "大一暑假": (2019, 7, 2019, 8),
    "大二上": (2019, 9, 2020, 1),
    "大二下": (2020, 3, 2020, 8),
    "大二寒假": (2020, 1, 2020, 2),
    "大二暑假": (2020, 7, 2020, 8),
    "大三上": (2020, 9, 2021, 1),
    "大三下": (2021, 3, 2021, 8),
    "大三寒假": (2021, 1, 2021, 2),
    "大三暑假": (2021, 7, 2021, 8),
    "大四上": (2021, 9, 2022, 1),
    "大四下": (2022, 3, 2022, 8),
    "大四寒假": (2022, 1, 2022, 2),
    "大四暑假": (2022, 7, 2022, 8),
    "大五上": (2022, 9, 2023, 1),
    "大五下": (2023, 3, 2023, 8),
    "大五寒假": (2023, 1, 2023, 2),
    "大五暑假": (2023, 7, 2023, 8),
    "博一上": (2023, 9, 2024, 1),
    "博一下": (2024, 3, 2024, 8),
    "博一寒假": (2024, 1, 2024, 2),
    "博一暑假": (2024, 7, 2024, 8),
    "博二上": (2024, 9, 2025, 1),
    "博二下": (2025, 3, 2025, 8),
    "博二寒假": (2025, 1, 2025, 2),
    "博二暑假": (2025, 7, 2025, 8),
    "博三上": (2025, 9, 2026, 1),
    "博三下": (2026, 3, 2026, 8),
    "博三寒假": (2026, 1, 2026, 2),
    "博三暑假": (2026, 7, 2026, 8),
    "博四上": (2026, 9, 2027, 1),
    "博四下": (2027, 3, 2027, 8),
}


def parse_explicit_date_range(filename: str) -> tuple[int, int, int, int] | None:
    """从文件名中解析明确的年月范围，如 (202401-202412)。

    Returns:
        (start_year, start_month, end_year, end_month) 或 None
    """
    m = re.search(r"[（(](\d{4})(\d{2})-(\d{4})(\d{2})[）)]", filename)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return None


def parse_semester_from_filename(filename: str) -> tuple[int, int, int, int] | None:
    """从文件名解析学期信息，返回对应的年份范围。

    处理复合文件名，如 "大二上+寒假.xlsx" → 取最早开始和最晚结束。
    """
    # 先检查是否有明确年份范围
    explicit = parse_explicit_date_range(filename)
    if explicit:
        return explicit

    # 从文件名中提取所有匹配的学期标识
    # 按长度降序排列key以优先匹配更长的模式
    sorted_keys = sorted(SEMESTER_YEAR_MAP.keys(), key=len, reverse=True)

    matched_ranges: list[tuple[int, int, int, int]] = []
    remaining = filename

    for key in sorted_keys:
        if key in remaining:
            matched_ranges.append(SEMESTER_YEAR_MAP[key])
            remaining = remaining.replace(key, "", 1)

    # 处理仅含 "寒假" / "暑假" 但前面有学期前缀的情况
    # 例如 "大三上寒假" 已在上面匹配到 "大三上" 和 "大三寒假"
    # 如果没有匹配到任何，尝试从文件名提取基础学期
    if not matched_ranges:
        # 尝试匹配 "大X" 或 "博X" 模式
        m = re.search(r"(大[一二三四五]|博[一二三四五六])", filename)
        if m:
            base = m.group(1)
            # 判断上/下学期
            if "上" in filename or "寒假" in filename:
                key = f"{base}上"
                if key in SEMESTER_YEAR_MAP:
                    matched_ranges.append(SEMESTER_YEAR_MAP[key])
            if "下" in filename or "暑假" in filename:
                key = f"{base}下"
                if key in SEMESTER_YEAR_MAP:
                    matched_ranges.append(SEMESTER_YEAR_MAP[key])

    if not matched_ranges:
        return None

    # 取所有匹配范围的最早开始和最晚结束
    start_year = min(r[0] for r in matched_ranges)
    start_month = min(r[1] for r in matched_ranges if r[0] == start_year)
    end_year = max(r[2] for r in matched_ranges)
    end_month = max(r[3] for r in matched_ranges if r[2] == end_year)

    return start_year, start_month, end_year, end_month


def correct_date(
    raw_date: date | datetime,
    year_range: tuple[int, int, int, int],
) -> date | None:
    """校正日期的年份。

    Excel中的日期可能年份错误（如显示2026年但实际是2020年），
    根据学期的年份范围和日期的月份推算正确年份。

    Args:
        raw_date: 从Excel读取的原始日期
        year_range: (start_year, start_month, end_year, end_month)

    Returns:
        校正后的日期，如果无法校正返回 None
    """
    if isinstance(raw_date, datetime):
        raw_date = raw_date.date()

    month = raw_date.month
    day = raw_date.day
    start_year, start_month, end_year, end_month = year_range

    # 根据月份判断应该属于哪一年
    # 如果文件跨年（如9月到次年2月），前半段用start_year，后半段用end_year
    if start_year == end_year:
        corrected_year = start_year
    elif month >= start_month:
        corrected_year = start_year
    else:
        corrected_year = end_year

    try:
        return date(corrected_year, month, day)
    except ValueError:
        # 处理闰年等边界情况（如2月29日在非闰年）
        if month == 2 and day == 29:
            return date(corrected_year, 2, 28)
        return None


def parse_date_from_cell(value) -> date | None:
    """从单元格值解析日期。

    支持：
    - datetime/date 对象（openpyxl 自动解析的Excel日期）
    - 字符串格式：YYYY-MM-DD, YYYY/MM/DD, MM-DD, M月D日 等
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    # YYYY-MM-DD or YYYY/MM/DD
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    # MM-DD or MM/DD (无年份，需后续校正)
    for fmt in ("%m-%d", "%m/%d", "%m.%d"):
        try:
            d = datetime.strptime(text, fmt).date()
            # 返回一个占位年份为1900的日期，后续由correct_date校正
            return d.replace(year=1900)
        except ValueError:
            continue

    # X月X日
    m = re.match(r"(\d{1,2})月(\d{1,2})日?", text)
    if m:
        try:
            return date(1900, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None

    return None
