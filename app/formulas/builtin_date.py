"""Excel-style date functions using Python date values."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Any


def _date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(value))
    if isinstance(value, str):
        return date.fromisoformat(value.strip()[:10])
    raise ValueError("#VALUE!")


def DATE(year: Any, month: Any, day: Any) -> date:  # noqa: N802
    year_value, month_value = int(float(year)), int(float(month))
    year_value += (month_value - 1) // 12
    month_value = (month_value - 1) % 12 + 1
    return date(year_value, month_value, 1) + timedelta(days=int(float(day)) - 1)


def TODAY() -> date:  # noqa: N802
    return date.today()


def NOW() -> datetime:  # noqa: N802
    return datetime.now()


def YEAR(value: Any) -> float:  # noqa: N802
    return float(_date(value).year)


def MONTH(value: Any) -> float:  # noqa: N802
    return float(_date(value).month)


def DAY(value: Any) -> float:  # noqa: N802
    return float(_date(value).day)


def EDATE(start_date: Any, months: Any) -> date:  # noqa: N802
    source = _date(start_date)
    month_index = source.year * 12 + source.month - 1 + int(float(months))
    year, month = divmod(month_index, 12)
    return date(year, month + 1, min(source.day, calendar.monthrange(year, month + 1)[1]))


def EOMONTH(start_date: Any, months: Any) -> date:  # noqa: N802
    shifted = EDATE(start_date, int(float(months)) + 1)
    return date(shifted.year, shifted.month, 1) - timedelta(days=1)


def DAYS(end_date: Any, start_date: Any) -> float:  # noqa: N802
    return float((_date(end_date) - _date(start_date)).days)
