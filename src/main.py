from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import re


# ============
# Configurações
# ============
EXPORT_DIR = Path("exports")
OUT_DIR = Path("out")

# Aqui você define "quem é você" pelo seu nome no GymRats
MY_FULL_NAME = "Jones Maromba"  # ajuste se no app estiver diferente

# Atividades que vamos considerar "cardio"
CARDIO_ACTIVITIES = {
    "running",
    "treadmill",
    "mixed_cardio",
    "walking",
}

TZ_SP = ZoneInfo("America/Sao_Paulo")

NATIONAL_HOLIDAYS_2026 = {
    date(2026, 1, 1),   # Confraternização Universal
    date(2026, 4, 3),   # Paixão de Cristo
    date(2026, 4, 21),  # Tiradentes
    date(2026, 5, 1),   # Dia do Trabalho
    date(2026, 9, 7),   # Independência do Brasil
    date(2026, 10, 12), # Nossa Senhora Aparecida
    date(2026, 11, 2),  # Finados
    date(2026, 11, 15), # Proclamação da República
    date(2026, 11, 20), # Consciência Negra
    date(2026, 12, 25), # Natal
}

# =====================
# Funções utilitárias
# =====================
def load_json(path: Path) -> Dict[str, Any]:
    """Lê o arquivo JSON e devolve um dict Python."""
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def parse_iso_datetime_to_sp_day(value: str) -> date:
    """
    Converte a string ISO em UTC (Z) para a data em America/Sao_Paulo.
    """
    dt_utc = datetime.fromisoformat(value.replace("Z", "+00:00"))
    dt_sp = dt_utc.astimezone(TZ_SP)
    return dt_sp.date()


def parse_distance_km(value: Optional[str]) -> Optional[float]:
    """
    Converte distância vinda como string no JSON para float.
    No seu export, aparece '2,6' (vírgula decimal), então normalizamos para ponto.
    IMPORTANTE: apesar do campo chamar distance_miles, vamos tratar como KM (decisão do projeto).
    """
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None
    

def is_ignored_day(day: date) -> bool:
    """
    Retorna True se a data deve ser ignorada:
    - fim de semana (sábado/domingo)
    - feriado nacional 2026
    """
    is_weekend = day.weekday() >= 5  # 5 = sábado, 6 = domingo
    is_holiday = day in NATIONAL_HOLIDAYS_2026
    return is_weekend or is_holiday
# ==========================
# Extração: members (lookup)
# ==========================
def build_member_lookup(data: Dict[str, Any]) -> Dict[int, str]:
    """
    Cria um dicionário {account_id: full_name} a partir de data['members'].
    """
    lookup: Dict[int, str] = {}
    for m in data.get("members", []):
        account_id = m.get("id")
        full_name = m.get("full_name")
        if isinstance(account_id, int) and isinstance(full_name, str):
            lookup[account_id] = full_name
    return lookup


def find_my_account_id(member_lookup: Dict[int, str], my_name: str) -> Optional[int]:
    """
    Acha seu account_id pelo nome completo.
    (Se não achar, você pode definir manualmente depois.)
    """
    for account_id, full_name in member_lookup.items():
        if full_name.strip().lower() == my_name.strip().lower():
            return account_id
    return None

def extract_winners_daily(df_leader: pd.DataFrame) -> pd.DataFrame:
        """
        Recebe o leaderboard diário (já filtrado por dias válidos) e retorna os vencedores por dia.
        Se houver empate no 1º lugar, retorna múltiplas linhas para o mesmo dia e marca tie=True.
        """
        if df_leader.empty:
            return df_leader

        # menor rank = 1 (melhor posição)
        top = df_leader[df_leader["rank"] == 1].copy()

        # detecta empate: mais de 1 vencedor no mesmo dia
        winners_count = top.groupby("date")["full_name"].transform("count")
        top["tie"] = winners_count > 1

        # renomeia para ficar “bonito”
        top = top.rename(
            columns={
                "full_name": "winner_full_name",
                "points_day": "winner_points_day",
            }
        )

        # seleciona só o que interessa
        top = top[["date", "winner_full_name", "winner_points_day", "tie"]].sort_values(["date", "winner_full_name"])
        return top
def extract_champions_weekly(df_leader: pd.DataFrame) -> pd.DataFrame:
    """
    Campeão da semana = soma de points_day dentro da semana (segunda a domingo),
    considerando apenas dias válidos (df_leader já vem filtrado).
    week_start = data da segunda-feira daquela semana.
    Se houver empate no topo, retorna múltiplas linhas e marca tie=True.
    """
    if df_leader.empty:
        return df_leader

    tmp = df_leader.copy()
    tmp["date"] = pd.to_datetime(tmp["date"])

    # week_start = segunda-feira da semana (ISO-like)
    tmp["week_start"] = (tmp["date"] - pd.to_timedelta(tmp["date"].dt.weekday, unit="D")).dt.date

    # soma de pontos por semana e membro
    weekly = (
        tmp.groupby(["week_start", "account_id", "full_name"], as_index=False)
        .agg(champion_points_week=("points_day", "sum"))
    )

    # rank semanal (1 = maior pontuação)
    weekly["rank_week"] = weekly.groupby("week_start")["champion_points_week"].rank(
        method="dense", ascending=False
    ).astype(int)

    top = weekly[weekly["rank_week"] == 1].copy()

    # empate: mais de 1 campeão na mesma semana
    top["tie"] = top.groupby("week_start")["full_name"].transform("count") > 1

    top = top.rename(columns={"full_name": "champion_full_name"})
    top["champion_points_week"] = top["champion_points_week"].round(6)

    return top[["week_start", "champion_full_name", "champion_points_week", "tie"]].sort_values(
        ["week_start", "champion_full_name"]
    )

def extract_my_cardio_weekly_km(df_cardio: pd.DataFrame) -> pd.DataFrame:
    """
    Soma a distância (km) por semana (segunda-feira como início).
    """
    if df_cardio.empty:
        return df_cardio

    tmp = df_cardio.copy()
    tmp["date"] = pd.to_datetime(tmp["date"])

    # remove linhas sem distância (NaN)
    tmp = tmp.dropna(subset=["distance_km"])

    # week_start = segunda-feira da semana
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

    # total_minutes pode virar NaN se não houver duração em nenhuma linha
    if "total_minutes" in weekly.columns:
        weekly["total_minutes"] = weekly["total_minutes"].fillna(0).round(2)

    # pace médio da semana (min/km) = total_min / total_km
    weekly["avg_pace_min_per_km"] = (weekly["total_minutes"] / weekly["total_km"]).replace([pd.NA, float("inf")], pd.NA)
    weekly["avg_pace_min_per_km"] = weekly["avg_pace_min_per_km"].round(2)

    return weekly


def extract_my_cardio_progress(df_weekly: pd.DataFrame) -> pd.DataFrame:
    """
    Cria uma tabela de evolução:
    - km acumulado
    - melhor semana (maior km até o momento)
    """
    if df_weekly.empty:
        return df_weekly

    out = df_weekly.copy().sort_values("week_start")
    out["cumulative_km"] = out["total_km"].cumsum().round(2)
    out["best_week_km_so_far"] = out["total_km"].cummax().round(2)

    return out[[
        "week_start",
        "total_km",
        "sessions",
        "total_minutes",
        "avg_pace_min_per_km",
        "cumulative_km",
        "best_week_km_so_far",
    ]]

EXPORT_FILENAME_PATTERN = re.compile(
    r"^gym-rats_export-?\d{2}-\d{2}-\d{2}\.json$"
)

def list_export_files(export_dir: Path) -> List[Path]:
    """
    Lista apenas arquivos que seguem o padrão esperado de export.
    """
    valid_files = []

    for p in export_dir.glob("*.json"):
        if EXPORT_FILENAME_PATTERN.match(p.name):
            valid_files.append(p)
        else:
            print(f"[IGNORADO] Nome inválido: {p.name}")

    return sorted(valid_files)

def dedupe_cardio(df_cardio: pd.DataFrame) -> pd.DataFrame:
    """
    Remove duplicatas quando você junta vários exports semanais.
    Prioridade:
    - se workout_id existe: usa workout_id como chave
    - senão: usa (date, start_time, activity, distance_km, duration_min)
    """
    if df_cardio.empty:
        return df_cardio

    df = df_cardio.copy()

    # chave primária preferencial
    has_workout = df["workout_id"].notna()

    df_with = df[has_workout].drop_duplicates(subset=["workout_id"], keep="first")
    df_without = df[~has_workout].drop_duplicates(
        subset=["date", "start_time", "activity", "distance_km", "duration_min"],
        keep="first",
    )

    out = pd.concat([df_with, df_without], ignore_index=True)
    out = out.sort_values(["date", "activity"]).reset_index(drop=True)
    return out

def extract_checkins_raw(data: Dict[str, Any], member_lookup: Dict[int, str]) -> pd.DataFrame:
    """
    Extrai check-ins em formato raw (1 linha por check-in) para permitir deduplicação
    antes de agregar por dia.
    """
    rows: List[Dict[str, Any]] = []

    for ci in data.get("check_ins", []):
        occurred_at = ci.get("occurred_at")
        account_id = ci.get("account_id")
        points = ci.get("points")

        if not (isinstance(occurred_at, str) and isinstance(account_id, int) and points is not None):
            continue

        # dia em São Paulo
        day_date = parse_iso_datetime_to_sp_day(occurred_at)

        # regra: ignora dias inválidos
        if is_ignored_day(day_date):
            continue

        try:
            pts = float(points)
        except (TypeError, ValueError):
            continue

        # chave composta para dedupe
        # (account_id + occurred_at + points) costuma ser suficiente
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


def leaderboard_from_raw_checkins(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Agrega raw check-ins (já deduplicados e filtrados) em leaderboard diário.
    """
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

def write_run_manifest(
    out_dir: Path,
    files: List[Path],
    df_leader: pd.DataFrame,
    df_cardio: pd.DataFrame,
) -> None:
    """
    Salva um arquivo com informações da execução.
    """
    manifest = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "processed_files_count": len(files),
        "processed_files": [f.name for f in files],
        "leaderboard_rows": int(len(df_leader)),
        "cardio_rows": int(len(df_cardio)),
    }

    with (out_dir / "run_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

# ==========================
# 1) Leaderboard diário
# ==========================
def extract_leaderboard_daily(data: Dict[str, Any], member_lookup: Dict[int, str]) -> pd.DataFrame:
    """
    Produz um DataFrame com:
    - date (YYYY-MM-DD)
    - account_id
    - full_name
    - points_day (soma de pontos no dia)
    - rank (1 = maior pontuação)
    """
    rows: List[Dict[str, Any]] = []

    for ci in data.get("check_ins", []):
        occurred_at = ci.get("occurred_at")
        account_id = ci.get("account_id")
        points = ci.get("points")

        if not (isinstance(occurred_at, str) and isinstance(account_id, int) and points is not None):
            continue

        day_date = parse_iso_datetime_to_sp_day(occurred_at)

# regra: ignora fins de semana e feriados nacionais
        if is_ignored_day(day_date):
            continue

        day = day_date.isoformat()

        try:
            pts = float(points)
        except (TypeError, ValueError):
            continue

        rows.append(
            {
                "date": day,
                "account_id": account_id,
                "full_name": member_lookup.get(account_id, f"account_{account_id}"),
                "points": pts,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # soma de pontos por dia e membro
    out = (
        df.groupby(["date", "account_id", "full_name"], as_index=False)
        .agg(points_day=("points", "sum"))
    )

    # ranking por dia (maior pontos = rank 1)
    out["rank"] = out.groupby("date")["points_day"].rank(method="dense", ascending=False).astype(int)

    out = out.sort_values(["date", "rank", "full_name"])
    out["points_day"] = out["points_day"].round(6)
    return out


# ==========================
# 2) Cardio (por atividade)
# ==========================
def extract_my_cardio_sessions(
    data: Dict[str, Any],
    member_lookup: Dict[int, str],
    my_account_id: int,
) -> pd.DataFrame:
    """
    Extrai cardio baseado em check_in_activities.
    Cada linha = 1 atividade cardio (running/treadmill/...) dentro de um check-in.
    """
    rows: List[Dict[str, Any]] = []

    for ci in data.get("check_ins", []):
        account_id = ci.get("account_id")
        if account_id != my_account_id:
            continue

        occurred_at = ci.get("occurred_at")
        if not isinstance(occurred_at, str):
            continue

        day_date = parse_iso_datetime_to_sp_day(occurred_at)
        day = day_date.isoformat()

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
                    "date": day,
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

    df = df.sort_values(["date", "activity"])
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not EXPORT_DIR.exists():
        raise SystemExit(f"Pasta não encontrada: {EXPORT_DIR}")

    files = list_export_files(EXPORT_DIR)
    if not files:
        raise SystemExit(f"Nenhum JSON encontrado em: {EXPORT_DIR}")

    raw_checkins_all = []
    cardio_all = []

    # Vamos assumir que a lista de members é consistente entre exports.
    # Pegamos do primeiro arquivo para montar lookup e achar seu account_id.
    first_data = load_json(files[0])
    member_lookup = build_member_lookup(first_data)

    my_account_id = find_my_account_id(member_lookup, MY_FULL_NAME)
    if my_account_id is None:
        raise SystemExit(
            f"Não achei '{MY_FULL_NAME}' em members. "
            "Veja o full_name exato no export ou defina manualmente."
        )

    # Processa todos os exports
    for p in files:
        data = load_json(p)

        # Se members mudar ao longo do tempo, você pode recomputar lookup por arquivo.
        # Por enquanto, reaproveitamos o primeiro.
        raw_checkins_all.append(extract_checkins_raw(data, member_lookup))
        cardio_all.append(extract_my_cardio_sessions(data, member_lookup, my_account_id))

    df_raw = pd.concat(raw_checkins_all, ignore_index=True)
    if not df_raw.empty:
        df_raw = df_raw.drop_duplicates(subset=["dedupe_key"], keep="first")

    df_leader = leaderboard_from_raw_checkins(df_raw)
    df_leader.to_csv(OUT_DIR / "leaderboard_daily.csv", index=False, encoding="utf-8")

    df_winners = extract_winners_daily(df_leader)
    df_winners.to_csv(OUT_DIR / "winners_daily.csv", index=False, encoding="utf-8")

    df_champions_week = extract_champions_weekly(df_leader)
    df_champions_week.to_csv(OUT_DIR / "champions_weekly.csv", index=False, encoding="utf-8")

    df_cardio = pd.concat(cardio_all, ignore_index=True)
    df_cardio = dedupe_cardio(df_cardio)
    df_cardio.to_csv(OUT_DIR / "my_cardio_sessions.csv", index=False, encoding="utf-8")

    df_cardio_weekly = extract_my_cardio_weekly_km(df_cardio)
    df_cardio_weekly.to_csv(OUT_DIR / "my_cardio_weekly_km.csv", index=False, encoding="utf-8")

    df_progress = extract_my_cardio_progress(df_cardio_weekly)
    df_progress.to_csv(OUT_DIR / "my_cardio_progress.csv", index=False, encoding="utf-8")

    print(f"OK! Processados {len(files)} export(s). Saídas em: {OUT_DIR}/")

    write_run_manifest(
        OUT_DIR,
        files,
        df_leader,
        df_cardio,
    )

if __name__ == "__main__":
    main()