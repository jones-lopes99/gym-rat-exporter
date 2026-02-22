from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, date
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


# ============
# Configurações
# ============
EXPORT_PATH = Path("exports/gym-rats_export-22-02-26.json")
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

        dt = parse_iso_datetime(occurred_at)
        day = dt.date().isoformat()

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

    if not EXPORT_PATH.exists():
        raise SystemExit(f"Arquivo não encontrado: {EXPORT_PATH}")

    data = load_json(EXPORT_PATH)

    member_lookup = build_member_lookup(data)
    my_account_id = find_my_account_id(member_lookup, MY_FULL_NAME)

    if my_account_id is None:
        raise SystemExit(
            f"Não achei '{MY_FULL_NAME}' em members. "
            "Abra o JSON e veja o seu full_name exato, ou defina my_account_id manualmente."
        )

    # 1) Leaderboard diário
    df_leader = extract_leaderboard_daily(data, member_lookup)
    df_leader.to_csv(OUT_DIR / "leaderboard_daily.csv", index=False, encoding="utf-8")

    # 2) Meu cardio
    df_cardio = extract_my_cardio_sessions(data, member_lookup, my_account_id)
    df_cardio.to_csv(OUT_DIR / "my_cardio_sessions.csv", index=False, encoding="utf-8")

    print("OK! Gerados:")
    print("-", OUT_DIR / "leaderboard_daily.csv")
    print("-", OUT_DIR / "my_cardio_sessions.csv")


if __name__ == "__main__":
    main()