import pandas as pd

from src.transforms import (
    leaderboard_from_raw_checkins,
    extract_winners_daily,
    extract_champions_weekly,
)

from src.transforms import dedupe_cardio

def test_daily_ranking_and_tie_detection():
    # Simula check-ins já filtrados e deduplicados
    df_raw = pd.DataFrame(
        [
            {"date": "2026-03-17", "account_id": 1, "full_name": "Alice", "points": 10, "dedupe_key": "1"},
            {"date": "2026-03-17", "account_id": 2, "full_name": "Bob", "points": 10, "dedupe_key": "2"},
            {"date": "2026-03-17", "account_id": 3, "full_name": "Carol", "points": 5, "dedupe_key": "3"},
        ]
    )

    df_leader = leaderboard_from_raw_checkins(df_raw)

    # Alice e Bob devem estar rank 1
    rank_1 = df_leader[df_leader["rank"] == 1]
    assert len(rank_1) == 2

    df_winners = extract_winners_daily(df_leader)

    # Deve detectar empate
    assert len(df_winners) == 2
    assert df_winners["tie"].all()


def test_weekly_champion():
    # Dois dias na mesma semana
    df_leader = pd.DataFrame(
        [
            {"date": "2026-03-16", "account_id": 1, "full_name": "Alice", "points_day": 10, "rank": 1},
            {"date": "2026-03-17", "account_id": 1, "full_name": "Alice", "points_day": 5, "rank": 1},
            {"date": "2026-03-16", "account_id": 2, "full_name": "Bob", "points_day": 8, "rank": 2},
        ]
    )

    df_champ = extract_champions_weekly(df_leader)

    # Alice somou 15, Bob 8
    assert len(df_champ) == 1
    assert df_champ.iloc[0]["champion_full_name"] == "Alice"
    assert df_champ.iloc[0]["champion_points_week"] == 15

def test_dedupe_cardio_prefers_workout_id():
    df = pd.DataFrame(
        [
            # Duplicado pelo mesmo workout_id (deve virar 1)
            {
                "date": "2026-03-17",
                "start_time": "2026-03-17T10:00:00Z",
                "activity": "running",
                "distance_km": 5.0,
                "duration_min": 30.0,
                "workout_id": 999,
            },
            {
                "date": "2026-03-17",
                "start_time": "2026-03-17T10:00:00Z",
                "activity": "running",
                "distance_km": 5.0,
                "duration_min": 30.0,
                "workout_id": 999,
            },
            # Outro workout_id diferente (deve ficar)
            {
                "date": "2026-03-17",
                "start_time": "2026-03-17T18:00:00Z",
                "activity": "treadmill",
                "distance_km": 3.0,
                "duration_min": 20.0,
                "workout_id": 1000,
            },
        ]
    )

    out = dedupe_cardio(df)

    # Esperado: 2 linhas (999 deduped + 1000)
    assert len(out) == 2
    assert set(out["workout_id"].dropna().astype(int).tolist()) == {999, 1000}


def test_dedupe_cardio_fallback_composite_key_when_no_workout_id():
    df = pd.DataFrame(
        [
            # Sem workout_id -> dedupe por (date, start_time, activity, distance, duration)
            {
                "date": "2026-03-17",
                "start_time": "2026-03-17T10:00:00Z",
                "activity": "running",
                "distance_km": 5.0,
                "duration_min": 30.0,
                "workout_id": None,
            },
            {
                "date": "2026-03-17",
                "start_time": "2026-03-17T10:00:00Z",
                "activity": "running",
                "distance_km": 5.0,
                "duration_min": 30.0,
                "workout_id": None,
            },
            # Mudou distância -> deve ser considerado outro registro
            {
                "date": "2026-03-17",
                "start_time": "2026-03-17T10:00:00Z",
                "activity": "running",
                "distance_km": 6.0,
                "duration_min": 35.0,
                "workout_id": None,
            },
        ]
    )

    out = dedupe_cardio(df)

    # Esperado: 2 linhas (os dois iguais viram 1, o de 6km permanece)
    assert len(out) == 2
    assert sorted(out["distance_km"].tolist()) == [5.0, 6.0]