from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from .time_utils import is_ignored_day, parse_iso_datetime_to_sp_day


CARDIO_ACTIVITIES = {"running", "treadmill", "mixed_cardio", "walking"}


def parse_distance_km(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def build_member_lookup(data: Dict[str, Any]) -> Dict[int, str]:
    lookup: Dict[int, str] = {}
    for m in data.get("members", []):
        account_id = m.get("id")
        full_name = m.get("full_name")
        if isinstance(account_id, int) and isinstance(full_name, str):
            lookup[account_id] = full_name
    return lookup


def find_account_id_by_name(member_lookup: Dict[int, str], full_name: str) -> Optional[int]:
    target = full_name.strip().lower()
    for account_id, name in member_lookup.items():
        if name.strip().lower() == target:
            return account_id
    return None


def extract_checkins_raw(
    data: Dict[str, Any],
    member_lookup: Dict[int, str],
    holidays: set[date],
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for ci in data.get("check_ins", []):
        occurred_at = ci.get("occurred_at")
        account_id = ci.get("account_id")
        points = ci.get("points")

        if not (isinstance(occurred_at, str) and isinstance(account_id, int) and points is not None):
            continue

        day_date = parse_iso_datetime_to_sp_day(occurred_at)
        if is_ignored_day(day_date, holidays):
            continue

        try:
            pts = float(points)
        except (TypeError, ValueError):
            continue

        dedupe_key = f"{account_id}|{occurred_at}|{pts}"

        rows.append(
            {
                "date": day_date.isoformat(),
                "occurred_at": occurred_at,
                "account_id": account_id,
                "full_name": member_lookup.get(account_id, f"account_{account_id}"),
                "points": pts,
                "dedupe_key": dedupe_key,
            }
        )

    return pd.DataFrame(rows)


def extract_my_cardio_sessions(
    data: Dict[str, Any],
    member_lookup: Dict[int, str],
    my_account_id: int,
) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    for ci in data.get("check_ins", []):
        if ci.get("account_id") != my_account_id:
            continue

        occurred_at = ci.get("occurred_at")
        if not isinstance(occurred_at, str):
            continue

        day_date = parse_iso_datetime_to_sp_day(occurred_at)

        for act in ci.get("check_in_activities", []) or []:
            platform_activity = act.get("platform_activity")
            if platform_activity not in CARDIO_ACTIVITIES:
                continue

            dist_km = parse_distance_km(act.get("distance_miles"))
            duration_ms = act.get("duration_millis")
            duration_min = None
            if isinstance(duration_ms, (int, float)):
                duration_min = round(float(duration_ms) / 60000.0, 2)

            rows.append(
                {
                    "date": day_date.isoformat(),
                    "start_time": act.get("start_time"),
                    "activity": platform_activity,
                    "distance_km": dist_km,
                    "duration_min": duration_min,
                    "workout_id": act.get("workout_id"),
                    "full_name": member_lookup.get(my_account_id, f"account_{my_account_id}"),
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values(["date", "activity"])