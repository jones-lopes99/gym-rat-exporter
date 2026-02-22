from __future__ import annotations

import pandas as pd


def leaderboard_from_raw_checkins(df_raw: pd.DataFrame) -> pd.DataFrame:
    if df_raw.empty:
        return df_raw

    out = (
        df_raw.groupby(["date", "account_id", "full_name"], as_index=False)
        .agg(points_day=("points", "sum"))
    )
    out["rank"] = out.groupby("date")["points_day"].rank(method="dense", ascending=False).astype(int)
    out = out.sort_values(["date", "rank", "full_name"])
    out["points_day"] = out["points_day"].round(6)
    return out


def extract_winners_daily(df_leader: pd.DataFrame) -> pd.DataFrame:
    if df_leader.empty:
        return df_leader

    top = df_leader[df_leader["rank"] == 1].copy()
    top["tie"] = top.groupby("date")["full_name"].transform("count") > 1
    top = top.rename(columns={"full_name": "winner_full_name", "points_day": "winner_points_day"})
    return top[["date", "winner_full_name", "winner_points_day", "tie"]].sort_values(["date", "winner_full_name"])


def extract_champions_weekly(df_leader: pd.DataFrame) -> pd.DataFrame:
    if df_leader.empty:
        return df_leader

    tmp = df_leader.copy()
    tmp["date"] = pd.to_datetime(tmp["date"])
    tmp["week_start"] = (tmp["date"] - pd.to_timedelta(tmp["date"].dt.weekday, unit="D")).dt.date

    weekly = (
        tmp.groupby(["week_start", "account_id", "full_name"], as_index=False)
        .agg(champion_points_week=("points_day", "sum"))
    )
    weekly["rank_week"] = weekly.groupby("week_start")["champion_points_week"].rank(
        method="dense", ascending=False
    ).astype(int)

    top = weekly[weekly["rank_week"] == 1].copy()
    top["tie"] = top.groupby("week_start")["full_name"].transform("count") > 1
    top = top.rename(columns={"full_name": "champion_full_name"})
    top["champion_points_week"] = top["champion_points_week"].round(6)

    return top[["week_start", "champion_full_name", "champion_points_week", "tie"]].sort_values(
        ["week_start", "champion_full_name"]
    )


def dedupe_cardio(df_cardio: pd.DataFrame) -> pd.DataFrame:
    if df_cardio.empty:
        return df_cardio

    df = df_cardio.copy()
    has_workout = df["workout_id"].notna()

    df_with = df[has_workout].drop_duplicates(subset=["workout_id"], keep="first")
    df_without = df[~has_workout].drop_duplicates(
        subset=["date", "start_time", "activity", "distance_km", "duration_min"],
        keep="first",
    )

    out = pd.concat([df_with, df_without], ignore_index=True)
    return out.sort_values(["date", "activity"]).reset_index(drop=True)


def extract_my_cardio_weekly_km(df_cardio: pd.DataFrame) -> pd.DataFrame:
    if df_cardio.empty:
        return df_cardio

    tmp = df_cardio.copy()
    tmp["date"] = pd.to_datetime(tmp["date"])
    tmp = tmp.dropna(subset=["distance_km"])
    tmp["week_start"] = (tmp["date"] - pd.to_timedelta(tmp["date"].dt.weekday, unit="D")).dt.date

    weekly = (
        tmp.groupby("week_start", as_index=False)
        .agg(
            total_km=("distance_km", "sum"),
            sessions=("distance_km", "count"),
            total_minutes=("duration_min", "sum"),
        )
        .sort_values("week_start")
    )

    weekly["total_km"] = weekly["total_km"].round(2)
    weekly["total_minutes"] = weekly["total_minutes"].fillna(0).round(2)

    weekly["avg_pace_min_per_km"] = (weekly["total_minutes"] / weekly["total_km"]).replace([pd.NA, float("inf")], pd.NA)
    weekly["avg_pace_min_per_km"] = weekly["avg_pace_min_per_km"].round(2)

    return weekly


def extract_my_cardio_progress(df_weekly: pd.DataFrame) -> pd.DataFrame:
    if df_weekly.empty:
        return df_weekly

    out = df_weekly.copy().sort_values("week_start")
    out["cumulative_km"] = out["total_km"].cumsum().round(2)
    out["best_week_km_so_far"] = out["total_km"].cummax().round(2)

    return out[
        [
            "week_start",
            "total_km",
            "sessions",
            "total_minutes",
            "avg_pace_min_per_km",
            "cumulative_km",
            "best_week_km_so_far",
        ]
    ]