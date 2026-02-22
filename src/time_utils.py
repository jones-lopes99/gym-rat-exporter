from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo


TZ_SP = ZoneInfo("America/Sao_Paulo")


def parse_iso_datetime_to_sp_day(value: str) -> date:
    dt_utc = datetime.fromisoformat(value.replace("Z", "+00:00"))
    dt_sp = dt_utc.astimezone(TZ_SP)
    return dt_sp.date()


def is_weekend(day: date) -> bool:
    return day.weekday() >= 5  # 5=sábado, 6=domingo


def is_ignored_day(day: date, holidays: set[date]) -> bool:
    return is_weekend(day) or (day in holidays)